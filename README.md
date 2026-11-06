<div align="center">

# 🌀 proxspray

**Spray a Proxmox VE + Ceph cluster onto bare metal, wired together over Thunderbolt 4.**

[![Proxmox VE 9](https://img.shields.io/badge/Proxmox%20VE-9.x-E57000?style=flat&logo=proxmox&logoColor=white)](https://www.proxmox.com/)
[![Ceph](https://img.shields.io/badge/Ceph-Tentacle-EF5C55?style=flat&logo=ceph&logoColor=white)](https://ceph.io/)
[![Thunderbolt 4](https://img.shields.io/badge/Thunderbolt-4-00A3E0?style=flat&logo=thunderbolt&logoColor=white)](https://www.intel.com/content/www/us/en/architecture-and-technology/thunderbolt/thunderbolt-technology-general.html)
[![Ansible](https://img.shields.io/badge/Ansible-%E2%89%A52.19-EE0000?style=flat&logo=ansible&logoColor=white)](https://www.ansible.com/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue?style=flat)](LICENSE)

</div>

---

An Ansible collection (`pfurtschellerp.proxspray`) that turns three mini PCs into a Proxmox VE cluster with Ceph storage, using a Thunderbolt 4 full mesh as the fast backbone between nodes.

## 🗺️ Topology

```
                        mgmt network · 10.10.1.0/24
              ───────┬──────────────┬──────────────┬───────
                     │              │              │
                ┌────┴───┐     ┌────┴───┐     ┌────┴───┐
                │ node-1 │═════│ node-2 │═════│ node-3 │
                └────╥───┘     └────────┘     └────╥───┘
                     ║                             ║
                     ╚═════════════════════════════╝

        ═══ Thunderbolt 4 full mesh · MTU 65520
            node-1 ⇄ node-2   10.100.0.0/30
            node-1 ⇄ node-3   10.100.0.4/30
            node-2 ⇄ node-3   10.100.0.8/30
```

## ✨ Features

| Status | Feature |
| :----: | ------- |
| ✅ | Thunderbolt networking: `thunderbolt-net` modules, stable `en05`/`en06` naming via systemd `.link` files |
| ✅ | Point-to-point IP addressing, IPv4 forwarding, connectivity checks |
| ✅ | Hotplug and boot-time bringup via udev rules and a systemd service |
| 🚧 | Proxmox VE cluster creation |
| 🚧 | Ceph (Tentacle) deployment on the Thunderbolt mesh |

## 🚀 Quick start

**Requirements:** Ansible ≥ 2.19, three Proxmox VE 9 nodes reachable over SSH, cabled in a Thunderbolt triangle.

```bash
# 1. Install collection dependencies
ansible-galaxy collection install community.general ansible.posix

# 2. Create your inventory from the sample
cp -r inventory/sample inventory/mycluster
$EDITOR inventory/mycluster/inventory.ini

# 3. Deploy
ansible-playbook -i inventory/mycluster/inventory.ini setup.yml
```

> 💡 Prefer a ready-made toolchain? Open the repo in the included **Dev Container** — Ansible, `ansible-lint` and all collections are preinstalled.

## ⚙️ Configuration

Each host needs a unique `node_id` (1–3), which selects its Thunderbolt IPs:

```ini
[all]
node-1 ansible_host=10.10.1.6 node_id=1
node-2 ansible_host=10.10.1.7 node_id=2
node-3 ansible_host=10.10.1.8 node_id=3
```

Key variables of the `thunderbolt` role (see [roles/thunderbolt/defaults/main.yml](roles/thunderbolt/defaults/main.yml)):

| Variable | Purpose |
| -------- | ------- |
| `thunderbolt_devices` | Interface name → PCI path (find it with `lspci \| grep -i thunderbolt`) |
| `thunderbolt_p2p_ips` | Per-node IP/prefix for each Thunderbolt interface |
| `thunderbolt_ping_targets` | Peer IPs pinged to verify the mesh after configuration |

## 📁 Layout

```
.
├── setup.yml              # Entry point
├── playbooks/             # Playbooks imported by setup.yml
├── roles/
│   └── thunderbolt/       # Thunderbolt mesh networking
├── inventory/sample/      # Example inventory
└── .devcontainer/         # Ready-to-use dev environment
```

## 📄 License

[GPL-3.0](LICENSE) © Patrick Pfurtscheller
