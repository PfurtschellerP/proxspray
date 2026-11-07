#!/usr/bin/env python
# Copyright (c) Patrick Pfurtscheller
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Remove a node's monitor and metadata server from the Proxmox VE ceph.conf.

`pveceph mon destroy` only works on the node of the monitor, which is gone
after a reinstall. This drops the [mon.<node>] and [mds.<node>] sections and
the monitor's address from mon_host, as pveceph would. Prints a JSON object
with "changed" and the removed "sections" and "addresses".
"""

import argparse
import json
import re
import sys

CONF = "/etc/pve/ceph.conf"
SECTION = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*$")
OPTION = re.compile(r"^(?P<indent>\s*)(?P<key>[^=\s]+)\s*=\s*(?P<value>.*?)\s*$")


def host_of(address):
    """Host part of a mon address like 10.0.0.1, 10.0.0.1:6789 or [v2:10.0.0.1:3300/0,v1:...]."""
    address = address.strip().strip("[]")
    address = re.sub(r"^v[12]:", "", address.split(",")[0])
    address = address.split("/")[0]
    if address.count(":") == 1:
        address = address.split(":")[0]
    return address


def forget(text, node):
    sections = {"mon." + node, "mds." + node}
    removed, addresses, kept = [], [], []
    current = None
    for line in text.splitlines(keepends=True):
        match = SECTION.match(line)
        if match:
            current = match.group("name").strip()
            if current in sections:
                removed.append(current)
        if current in sections:
            option = OPTION.match(line)
            if current.startswith("mon.") and option and option.group("key") in ("public_addr", "mon_addr"):
                addresses.append(host_of(option.group("value")))
            continue
        kept.append(line)

    result = []
    current = None
    for line in kept:
        match = SECTION.match(line)
        if match:
            current = match.group("name").strip()
        option = OPTION.match(line)
        if current == "global" and option and option.group("key") == "mon_host" and addresses:
            hosts = [h for h in re.split(r"[\s,]+", option.group("value")) if h and host_of(h) not in addresses]
            line = "%smon_host = %s\n" % (option.group("indent"), " ".join(hosts))
        result.append(line)
    return "".join(result), removed, addresses


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--node", required=True, help="Proxmox VE node name")
    parser.add_argument("--conf", default=CONF)
    parser.add_argument("--check", action="store_true", help="only report what would change")
    args = parser.parse_args()

    with open(args.conf) as handle:
        text = handle.read()
    new, removed, addresses = forget(text, args.node)
    changed = new != text
    # Written in place: the cluster file system does not support chmod/chown,
    # which a replacing move would need.
    if changed and not args.check:
        with open(args.conf, "w") as handle:
            handle.write(new)
    json.dump({"changed": changed, "sections": removed, "addresses": addresses}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
