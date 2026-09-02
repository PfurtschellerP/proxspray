FROM python:3.14.7-slim

ARG WORKSPACE_DIR=/workspaces/proxspray

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Install Ansible and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ssh

COPY requirements.txt /tmp/requirements.txt
COPY requirements.yml /tmp/requirements.yml
RUN pip3 install -r /tmp/requirements.txt
RUN ansible-galaxy collection install -r /tmp/requirements.yml

# Create a symlink to the workspace directory
RUN mkdir -p /usr/share/ansible/collections/ansible_collections/pfurtschellerp
RUN ln -s ${WORKSPACE_DIR} /usr/share/ansible/collections/ansible_collections/pfurtschellerp/proxyspray
