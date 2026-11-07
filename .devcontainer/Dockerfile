# Official Dev Container base image: Debian 13 (trixie, same as Proxmox VE 9),
# Python 3.14, git, openssh-client and a non-root "vscode" user.
FROM mcr.microsoft.com/devcontainers/python:3.14-trixie

# Tools to build the unattended installer ISOs (install_media role) from the
# Proxmox VE repository; the keyring checksum is the one Proxmox publishes.
ARG PROXMOX_KEYRING_SHA256=136673be77aba35dcce385b28737689ad64fd785a797e57897589aed08db6e45
RUN curl -fsSLo /usr/share/keyrings/proxmox-archive-keyring.gpg \
        https://enterprise.proxmox.com/debian/proxmox-archive-keyring-trixie.gpg \
    && echo "${PROXMOX_KEYRING_SHA256}  /usr/share/keyrings/proxmox-archive-keyring.gpg" | sha256sum --check --quiet \
    && printf '%s\n' \
        'Types: deb' \
        'URIs: http://download.proxmox.com/debian/pve' \
        'Suites: trixie' \
        'Components: pve-no-subscription' \
        'Signed-By: /usr/share/keyrings/proxmox-archive-keyring.gpg' \
        > /etc/apt/sources.list.d/proxmox.sources \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        proxmox-auto-install-assistant \
        xorriso \
    && rm -rf /var/lib/apt/lists/*

# Ansible tooling
COPY requirements.txt /tmp/devcontainer/requirements.txt
RUN pip3 install --disable-pip-version-check --no-cache-dir \
        -r /tmp/devcontainer/requirements.txt

# Collection dependencies, installed system-wide so every user can see them
COPY requirements.yml /tmp/devcontainer/requirements.yml
RUN ansible-galaxy collection install \
        -r /tmp/devcontainer/requirements.yml \
        -p /usr/share/ansible/collections \
    && rm -rf /tmp/devcontainer

# Custom shell prompt
COPY prompt.sh /usr/local/share/proxspray/prompt.sh
RUN echo 'source /usr/local/share/proxspray/prompt.sh' >> /home/vscode/.bashrc
