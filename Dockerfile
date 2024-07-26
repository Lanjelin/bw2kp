FROM python:3.11-slim-bookworm

ADD  bitwarden-to-keepass /bitwarden-to-keepass
COPY entrypoint.sh /

RUN apt-get update && \
    apt-get install -y --no-install-recommends wget unzip && \
    # wget -O "bw.zip" "https://vault.bitwarden.com/download/?app=cli&platform=linux" && \
    wget -O "bw.zip" "https://github.com/bitwarden/clients/releases/download/cli-v2024.6.0/bw-linux-2024.6.0.zip" && \
    unzip bw.zip && \
    chmod +x ./bw && \
    mv ./bw /usr/bin/bw && \
    apt-get purge -y --auto-remove wget unzip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf bw.zip && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /bitwarden-to-keepass/requirements.txt

VOLUME /exports
VOLUME /root/.config

SHELL ["/bin/bash", "-c"]
ENTRYPOINT "/entrypoint.sh"
