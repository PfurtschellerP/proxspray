#!/usr/bin/env bash
# Runs once after the container is created.
set -euo pipefail

# Make this repository resolvable as the pfurtschellerp.proxspray collection.
# ~/.ansible/collections is on Ansible's default collections path.
namespace_dir="${HOME}/.ansible/collections/ansible_collections/pfurtschellerp"
mkdir -p "${namespace_dir}"
ln -sfn "${PWD}" "${namespace_dir}/proxspray"

ansible --version | head -1
ansible-galaxy collection list pfurtschellerp.proxspray
