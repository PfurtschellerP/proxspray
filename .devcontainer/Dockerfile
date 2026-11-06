# Official Dev Container base image: Debian 13 (trixie, same as Proxmox VE 9),
# Python 3.14, git, openssh-client and a non-root "vscode" user.
FROM mcr.microsoft.com/devcontainers/python:3.14-trixie

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
