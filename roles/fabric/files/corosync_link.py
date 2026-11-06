#!/usr/bin/env python
# Copyright (c) Patrick Pfurtscheller
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Add or update a knet link in the Proxmox VE corosync configuration.

Follows the documented procedure: write corosync.conf.new, keep a backup in
corosync.conf.bak, move the new file into place and increase config_version.
Prints a JSON object with "changed", "preferred_link" and "config_version".
"""

import argparse
import json
import os
import re
import shutil
import sys

CONF = "/etc/pve/corosync.conf"


class ConfigError(Exception):
    pass


def parse(text):
    """Parse corosync.conf into nested lists of (key, value) and (name, [children])."""
    root = []
    stack = [root]
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("{"):
            block = (line[:-1].strip(), [])
            stack[-1].append(block)
            stack.append(block[1])
        elif line == "}":
            if len(stack) == 1:
                raise ConfigError("unbalanced '}' on line %d" % number)
            stack.pop()
        elif ":" in line:
            key, value = line.split(":", 1)
            stack[-1].append((key.strip(), value.strip()))
        else:
            raise ConfigError("cannot parse line %d: %s" % (number, line))
    if len(stack) != 1:
        raise ConfigError("unbalanced '{'")
    return root


def render(items, depth=0):
    lines = []
    for index, (key, value) in enumerate(items):
        indent = "  " * depth
        if isinstance(value, list):
            if depth == 0 and index > 0:
                lines.append("")
            lines.append("%s%s {" % (indent, key))
            lines.extend(render(value, depth + 1))
            lines.append("%s}" % indent)
        else:
            lines.append("%s%s: %s" % (indent, key, value))
    return lines


def blocks(items, name):
    return [value for key, value in items if key == name and isinstance(value, list)]


def get(items, key, default=None):
    for item_key, value in items:
        if item_key == key and not isinstance(value, list):
            return value
    return default


def set_value(items, key, value, after=None):
    """Set key to value; insert after the last key matching the regex `after`."""
    for index, (item_key, item_value) in enumerate(items):
        if item_key == key and not isinstance(item_value, list):
            if item_value == value:
                return False
            items[index] = (key, value)
            return True
    position = len(items)
    if after:
        matches = [i for i, (k, v) in enumerate(items) if re.match(after, k) and not isinstance(v, list)]
        if matches:
            position = matches[-1] + 1
    items.insert(position, (key, value))
    return True


def preferred_link(totem, nodes):
    """Link corosync uses while all links are up: highest priority, then lowest number."""
    links = set()
    for node in nodes:
        for key, value in node:
            match = re.match(r"^ring(\d+)_addr$", key)
            if match and not isinstance(value, list):
                links.add(int(match.group(1)))
    priorities = {}
    for interface in blocks(totem, "interface"):
        number = get(interface, "linknumber")
        priority = get(interface, "knet_link_priority")
        if number is not None and priority is not None:
            priorities[int(number)] = int(priority)
    return sorted(links, key=lambda link: (-priorities.get(link, 1), link))[0]


def update(config, linknumber, addresses):
    changed = False
    nodelists = blocks(config, "nodelist")
    totems = blocks(config, "totem")
    if len(nodelists) != 1 or len(totems) != 1:
        raise ConfigError("expected exactly one nodelist and one totem section")
    totem = totems[0]
    nodes = blocks(nodelists[0], "node")

    remaining = dict(addresses)
    for node in nodes:
        name = get(node, "name")
        if name not in remaining:
            raise ConfigError("cluster node %s has no fabric address" % name)
        changed |= set_value(node, "ring%d_addr" % linknumber, remaining.pop(name), after=r"^ring\d+_addr$")
    if remaining:
        raise ConfigError("not cluster members: %s" % ", ".join(sorted(remaining)))

    interfaces = blocks(totem, "interface")
    if not any(get(i, "linknumber") == str(linknumber) for i in interfaces):
        position = max([i for i, (k, v) in enumerate(totem) if k == "interface"] or [len(totem) - 1]) + 1
        totem.insert(position, ("interface", [("linknumber", str(linknumber))]))
        changed = True

    if changed:
        version = get(totem, "config_version")
        if version is None or not version.isdigit():
            raise ConfigError("totem.config_version is missing or not a number")
        set_value(totem, "config_version", str(int(version) + 1))

    return changed, preferred_link(totem, nodes), int(get(totem, "config_version"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linknumber", type=int, required=True)
    parser.add_argument("--address", action="append", default=[], metavar="NODE=IP", required=True)
    parser.add_argument("--check", action="store_true", help="only report what would change")
    parser.add_argument("--config", default=CONF)
    args = parser.parse_args()

    try:
        addresses = dict(item.split("=", 1) for item in args.address)
        with open(args.config) as handle:
            config = parse(handle.read())
        changed, preferred, version = update(config, args.linknumber, addresses)
        if changed and not args.check:
            new = args.config + ".new"
            with open(new, "w") as handle:
                handle.write("\n".join(render(config)) + "\n")
            shutil.copyfile(args.config, args.config + ".bak")
            os.rename(new, args.config)
    except (ConfigError, OSError, ValueError) as error:
        print(json.dumps({"failed": True, "msg": str(error)}))
        return 1

    print(json.dumps({"changed": changed, "preferred_link": preferred, "config_version": version}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
