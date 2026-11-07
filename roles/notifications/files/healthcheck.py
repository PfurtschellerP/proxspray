#!/usr/bin/env python
# Copyright (c) Patrick Pfurtscheller
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Health check of a proxspray node, run by proxspray-healthcheck.timer.

Checks what Proxmox VE does not report by itself: cluster quorum, offline
nodes, Ceph health and the Thunderbolt links (present, up, full speed).
Problems are mailed to root once they persist for the grace period, and again
when they are resolved. Proxmox VE forwards root's mail to its notification
targets (proxmox-mail-forward), e.g. Telegram or ntfy.

Cluster-wide checks (offline nodes, Ceph) run on the online node with the
lowest name only, so a problem is reported once, not by every node.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time

CONFIG = "/etc/proxspray/healthcheck.json"
STATE = "/var/lib/proxspray/healthcheck-state.json"


def run(args, timeout=30):
    """Return the output of a command, or None if it fails."""
    try:
        process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 universal_newlines=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return process.stdout if process.returncode == 0 else None


def read(path):
    try:
        with open(path) as handle:
            return handle.read().strip()
    except OSError:
        return None


def check_cluster(node):
    """Return (problems, leader): leader is True on the node that runs the cluster-wide checks."""
    output = run(["pvesh", "get", "/cluster/status", "--output-format", "json"])
    if output is None:
        return {"cluster": "Cannot read the cluster status on %s (pvesh get /cluster/status failed)." % node}, False
    entries = json.loads(output)
    cluster = next((entry for entry in entries if entry.get("type") == "cluster"), None)
    nodes = [entry for entry in entries if entry.get("type") == "node"]
    if cluster is None:
        # A single node without a cluster: it is its own leader.
        return {}, True
    problems = {}
    if not cluster.get("quorate"):
        problems["quorum"] = "The cluster is not quorate on %s; guests cannot be started or changed." % node
        return problems, False
    online = sorted(entry["name"] for entry in nodes if entry.get("online"))
    leader = bool(online) and online[0] == node
    offline = sorted(entry["name"] for entry in nodes if not entry.get("online"))
    if leader and offline:
        problems["nodes-offline"] = "Cluster nodes offline: %s." % ", ".join(offline)
    return problems, leader


def check_ceph(ignore):
    if not os.path.exists("/etc/pve/ceph.conf"):
        return {}
    output = run(["ceph", "health", "--format", "json"], timeout=20)
    if output is None:
        return {"ceph": "Cannot read the Ceph health (ceph health failed or timed out); check `ceph -s`."}
    health = json.loads(output)
    problems = {}
    for code, check in sorted(health.get("checks", {}).items()):
        if code in ignore:
            continue
        message = check.get("summary", {}).get("message", "")
        problems["ceph-" + code] = "Ceph %s: %s (%s)" % (check.get("severity", "HEALTH_WARN"), message, code)
    return problems


def link_speed(interface, direction):
    """Gb/s of one direction (speed per lane x lanes), or None if the kernel does not report it."""
    base = "/sys/class/net/%s/device/.." % interface
    speed = read("%s/%s_speed" % (base, direction))
    lanes = read("%s/%s_lanes" % (base, direction))
    try:
        return float(speed.split()[0]) * int(lanes)
    except (AttributeError, IndexError, ValueError):
        return None


def check_thunderbolt(node, interfaces, min_speed):
    problems = {}
    for interface in interfaces:
        key = "thunderbolt-" + interface
        if not os.path.exists("/sys/class/net/" + interface):
            problems[key] = ("Thunderbolt link %s on %s is down: no interface (cable unplugged or broken, or the peer "
                             "node is off). Traffic is rerouted through the third node." % (interface, node))
            continue
        state = read("/sys/class/net/%s/operstate" % interface)
        if state != "up":
            problems[key] = "Thunderbolt link %s on %s is %s." % (interface, node, state)
            continue
        if min_speed > 0:
            speeds = [link_speed(interface, direction) for direction in ("rx", "tx")]
            if None not in speeds and min(speeds) < min_speed:
                problems[key + "-speed"] = ("Thunderbolt link %s on %s runs at %g Gb/s, below %g Gb/s; check the cable."
                                            % (interface, node, min(speeds), min_speed))
    return problems


def collect(config):
    node = socket.gethostname().split(".")[0]
    problems, leader = check_cluster(node)
    if leader:
        problems.update(check_ceph(set(config.get("ceph_ignore", []))))
    problems.update(check_thunderbolt(node, config.get("thunderbolt_interfaces", []),
                                      float(config.get("thunderbolt_min_link_speed", 0))))
    return node, problems


def send(node, subject, lines):
    message = "To: root\nSubject: [proxspray] %s: %s\n\n%s\n" % (node, subject, "\n".join(lines))
    process = subprocess.run(["/usr/sbin/sendmail", "-t", "-oi"], input=message, universal_newlines=True, timeout=60, check=False)
    return process.returncode == 0


def load_state():
    try:
        with open(STATE) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_state(state):
    directory = os.path.dirname(STATE)
    if not os.path.isdir(directory):
        os.makedirs(directory, 0o755)
    new = STATE + ".new"
    with open(new, "w") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
    os.rename(new, STATE)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--print", action="store_true", help="print the current problems as JSON, send nothing")
    parser.add_argument("--test", action="store_true", help="send a test notification")
    parser.add_argument("--config", default=CONFIG)
    args = parser.parse_args()

    with open(args.config) as handle:
        config = json.load(handle)
    node, problems = collect(config)

    if args.print:
        print(json.dumps({"node": node, "problems": problems}, indent=2, sort_keys=True))
        return 0
    if args.test:
        return 0 if send(node, "test notification", ["The proxspray health check can send notifications."]) else 1

    now = time.time()
    grace = int(config.get("grace", 600))
    state = load_state()
    new_state = {}
    for key, message in problems.items():
        entry = state.get(key, {"since": now, "notified": False})
        entry["message"] = message
        new_state[key] = entry
    due = sorted(key for key, entry in new_state.items() if not entry["notified"] and now - entry["since"] >= grace)
    resolved = sorted(key for key, entry in state.items() if key not in new_state and entry.get("notified"))

    if due or resolved:
        lines = []
        if due:
            lines += ["New problems:"] + ["- " + new_state[key]["message"] for key in due] + [""]
        if resolved:
            lines += ["Resolved:"] + ["- " + state[key].get("message", key) for key in resolved] + [""]
        still = sorted(key for key, entry in new_state.items() if entry["notified"])
        if still:
            lines += ["Still open:"] + ["- " + new_state[key]["message"] for key in still] + [""]
        subject = ("%d new problem(s)" % len(due)) if due else ("%d problem(s) resolved" % len(resolved))
        if send(node, subject, lines):
            for key in due:
                new_state[key]["notified"] = True
        else:
            # Keep the resolved entries, so the next run tries again.
            for key in resolved:
                new_state[key] = state[key]
    save_state(new_state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
