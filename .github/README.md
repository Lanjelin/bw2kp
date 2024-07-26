# bitwarden-to-keepass

Export (most of) your Bitwarden items into KeePass database.  
Please make a backup should you run this against an existing database, as undesired results and corruption may happen.

## How it works?

It uses official [bitwarden-cli](https://bitwarden.com/help/article/cli/) client to export your items from Bitwarden vault and move them into your KeePass database - that includes logins (with TOTP seeds, URIs, custom fields, attachments, notes) and secure notes.

# Usage with docker (docker-compose) - recommended

- Clone this repository
- Edit `.env` file
  - ⚠️ make sure to set your own `DATABASE_PASSWORD` - used as password for KeePass database
  - Default and optional variables are commented out.
  - Protect this file, as it exposes everything needed to authenticate to Bitwarden, alternatively look into secrets handling.
- Run

```
docker compose up
```

- After the process is finished your database export is in `exports` directory

# TODO

- Take a second look at identities and cards.
- Make a proper readme with more examples
- Look if there is a way to edit/sync to an existing database, instead of writing duplicates.
