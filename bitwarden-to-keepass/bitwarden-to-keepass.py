import json
import logging
import os
import re
import subprocess
from argparse import ArgumentParser
from typing import Dict, List, Optional
from datetime import datetime

import folder as FolderType
from item import CustomFieldType, Item, ItemType
from pykeepass import PyKeePass, create_database
from pykeepass.entry import Entry as KPEntry
from pykeepass.exceptions import CredentialsError
from pykeepass.group import Group as KPGroup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s :: %(levelname)s :: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

kp: Optional[PyKeePass] = None

def bitwarden_to_keepass(args):
    global kp
    try:
        kp = PyKeePass(
            args.database_path,
            password=args.database_password,
            keyfile=args.database_keyfile,
        )
    except FileNotFoundError:
        logging.info("KeePass database does not exist, creating a new one.")
        kp = create_database(
            args.database_path,
            password=args.database_password,
            keyfile=args.database_keyfile,
        )
    except CredentialsError as e:
        logging.error(f"Wrong password for KeePass database: {e}")
        return

    # Archiving old group (pykepass cant handle deletion of binaries properly)
    if args.root_group is not None:
        existing_group = next((g for g in kp.root_group.subgroups if g.name == args.root_group), None)

        if existing_group:
            timestamp = datetime.now().strftime("%Y%m%d")
            archived_name = f"{args.root_group} {timestamp}"

            archive_group_name = args.archived_group or "Archived"
            archive_group = next((g for g in kp.root_group.subgroups if g.name == archive_group_name), None)
            if not archive_group:
                archive_group = kp.add_group(kp.root_group, archive_group_name)
                logging.info(f"Created '{archive_group_name}' group.")

            logging.info(f"Archiving group '{args.root_group}' as '{archived_name}'.")
            archived_group = kp.add_group(archive_group, archived_name)

            kp.move_group(existing_group, archived_group)

    folders = subprocess.check_output(
        [args.bw_path, "list", "folders", "--session", args.bw_session], encoding="utf8"
    )
    folders = json.loads(folders)
    groups_by_id = load_folders(folders)
    logging.info(f"Folders done ({len(groups_by_id)}).")

    items = subprocess.check_output(
        [args.bw_path, "list", "items", "--session", args.bw_session], encoding="utf8"
    )
    items = json.loads(items)
    logging.info(f"Starting to process {len(items)} items.")
    for item in items:
        # if item['type'] in [ItemType.CARD, ItemType.IDENTITY]:
        #     logging.warning(f'Skipping credit card or identity item "{item["name"]}".')
        #     continue

        bw_item = Item(item)

        is_duplicate_title = False
        try:
            while True:
                entry_title = (
                    bw_item.get_name()
                    if not is_duplicate_title
                    else "{name} - ({item_id}".format(
                        name=bw_item.get_name(), item_id=bw_item.get_id()
                    )
                )
                try:
                    entry = kp.add_entry(
                        destination_group=groups_by_id[bw_item.get_folder_id()],
                        title=entry_title,
                        username=bw_item.get_username(),
                        password=bw_item.get_password(),
                        notes=bw_item.get_notes(),
                    )
                    break
                except Exception as e:
                    if "already exists" in str(e):
                        is_duplicate_title = True
                        continue
                    raise

            totp_secret, totp_settings = bw_item.get_totp()
            if totp_secret and totp_settings:
                entry.set_custom_property("TOTP Seed", totp_secret, protect=True)
                entry.set_custom_property("TOTP Settings", totp_settings)

            uris = [uri["uri"] for uri in bw_item.get_uris()]
            set_kp_entry_urls(entry, uris)

            if item["type"] in [ItemType.CARD]:
                card_items = bw_item.get_card_fields()
                # for card_item in bw_item.get_card_fields():
                # bw_item.get_card_fields()[card_item],
                for card_item in card_items:
                    entry.set_custom_property(card_item, card_items[card_item])

            if item["type"] in [ItemType.IDENTITY]:
                identity_items = bw_item.get_identity_fields()
                # for identity_item in bw_item.get_identity_fields():
                # identity_item, bw_item.get_identity_fields()[identity_item]
                for identity_item in identity_items:
                    entry.set_custom_property(
                        identity_item, identity_items[identity_item]
                    )

            for field in bw_item.get_custom_fields():
                entry.set_custom_property(
                    field["name"],
                    field["value"],
                    protect=field["type"] == CustomFieldType.HIDDEN,
                )

            for attachment in bw_item.get_attachments():
                attachment_raw = subprocess.check_output(
                    [
                        args.bw_path,
                        "get",
                        "attachment",
                        attachment["id"],
                        "--raw",
                        "--itemid",
                        bw_item.get_id(),
                        "--session",
                        args.bw_session,
                    ]
                )
                attachment_id = kp.add_binary(attachment_raw)
                entry.add_attachment(attachment_id, attachment["fileName"])

        except Exception as e:
            logging.warning(
                f'Skipping item named "{item["name"]}" because of this error: {repr(e)}'
            )
            continue

    logging.info("Saving changes to KeePass database.")
    kp.save()
    logging.info("Export completed.")


def set_kp_entry_urls(entry: KPEntry, urls: List[str]) -> None:
    """Store a list of URLs comming from a Bitwarden entry in different
    attributes and custom properties of a KeePass entry, depending on whether
    it's an identifier for an Android or iOS app or it's a generic URL"""
    android_apps = ios_apps = extra_urls = 0

    for url in urls:
        match url.partition("://"):
            case ("androidapp", "://", app_id):
                # It's an Android app registered by Bitwarden's mobile app
                # Store multiple apps in AndroidApp, AndroidApp_1, etc. so that KeePassDX's autofill picks it up
                prop_name = (
                    "AndroidApp" if android_apps == 0 else f"AndroidApp_{android_apps}"
                )
                android_apps += 1
                entry.set_custom_property(prop_name, app_id)
            case ("iosapp", "://", app_id):
                # It's an iOS app registered by Bitwarden's mobile app
                # XXX Maybe properly set up autofill for a macOS/iPhone/iPad KeePass-compatible app like StrongBox or Keepassium
                ios_apps += 1
                entry.set_custom_property(f"iOS app #{ios_apps}", app_id)
            case _:
                # Assume it's a generic URL.
                # First one goes to the standard URL attribute and the remaining ones go to URL_1, URL_2 and so on
                if entry.url is None:
                    entry.url = url
                else:
                    extra_urls += 1
                    entry.set_custom_property(f"KP2A_URL_{extra_urls}", url)


def load_folders(folders) -> Dict[str, KPGroup]:
    # sort folders so that in the case of nested folders, the parents would be guaranteed to show up before the children
    folders.sort(key=lambda x: x["name"])

    # dict to store mapping of Bitwarden folder id to keepass group
    groups_by_id: Dict[str, KPGroup] = {}

    # build up folder tree
    folder_root: FolderType.Folder = FolderType.Folder(None)
    # if variable set
    if args.root_group:
        bw_group = kp.add_group(kp.root_group, args.root_group)
        folder_root.keepass_group = bw_group
    else:
        folder_root.keepass_group = kp.root_group
    groups_by_id[None] = folder_root.keepass_group

    for folder in folders:
        if folder["id"] is not None:
            new_folder: FolderType.Folder = FolderType.Folder(folder["id"])
            # regex lifted from https://github.com/bitwarden/jslib/blob/ecdd08624f61ccff8128b7cb3241f39e664e1c7f/common/src/services/folder.service.ts#L108
            folder_name_parts: List[str] = re.sub(
                r"^\/+|\/+$", "", folder["name"]
            ).split("/")
            FolderType.nested_traverse_insert(
                folder_root, folder_name_parts, new_folder, "/"
            )

    # create keepass groups based off folder tree
    def add_keepass_group(folder: FolderType.Folder):
        parent_group: KPGroup = folder.parent.keepass_group
        new_group: KPGroup = kp.add_group(parent_group, folder.name)
        folder.keepass_group = new_group
        groups_by_id[folder.id] = new_group

    FolderType.bfs_traverse_execute(folder_root, add_keepass_group)

    return groups_by_id


def check_args(args):
    if args.database_keyfile:
        if not os.path.isfile(args.database_keyfile) or not os.access(
            args.database_keyfile, os.R_OK
        ):
            logging.error("Key File for KeePass database is not readable.")
            return False

    if not os.path.isfile(args.bw_path) or not os.access(args.bw_path, os.X_OK):
        logging.error(
            "bitwarden-cli was not found or not executable. Did you set correct '--bw-path'?"
        )
        return False

    return True


def environ_or_required(key):
    return (
        {"default": os.environ.get(key)} if os.environ.get(key) else {"required": True}
    )


parser = ArgumentParser()
parser.add_argument(
    "--bw-session",
    help="Session generated from bitwarden-cli (bw login)",
    **environ_or_required("BW_SESSION"),
)
parser.add_argument(
    "--database-path",
    help="Path to KeePass database. If database does not exists it will be created.",
    **environ_or_required("DATABASE_PATH"),
)
parser.add_argument(
    "--database-password",
    help="Password for KeePass database",
    **environ_or_required("DATABASE_PASSWORD"),
)
parser.add_argument(
    "--database-keyfile",
    help="Path to Key File for KeePass database",
    default=os.environ.get("DATABASE_KEYFILE", None),
)
parser.add_argument(
    "--bw-path",
    help="Path for bw binary",
    default=os.environ.get("BW_PATH", "bw"),
)
parser.add_argument(
    "--root-group",
    help="Root group to store data from Bitwarden",
    default=os.environ.get("ROOT_GROUP", None),
)
parser.add_argument(
    "--archived-group",
    help="Archived group name to store old backups",
    default=os.environ.get("ARCHIVED_GROUP", None),
)
args = parser.parse_args()

check_args(args) and bitwarden_to_keepass(args)
