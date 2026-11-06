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

        ═══ Thunderbolt 4 full mesh · MTU 65520 · OpenFabric (Proxmox VE SDN)
            router IDs  node-1 10.100.0.1 · node-2 10.100.0.2 · node-3 10.100.0.3
            Ceph, migration and corosync link 1 run over the mesh; if a cable
            fails, traffic is rerouted through the third node.
            Corosync link 0 (preferred) stays on the management network.
```

## ✨ Features

| Status | Feature |
| :----: | ------- |
| ✅ | Proxmox VE essentials: deb822 repositories (enterprise / no-subscription / test), packages, `/etc/hosts`, timezone, NTP |
| ✅ | Thunderbolt links: `thunderbolt-net` modules, stable `en05`/`en06` naming via systemd `.link` files, MTU, hotplug and boot-time bringup |
| ✅ | Proxmox VE cluster creation and node join (over SSH, no root password needed) |
| ✅ | Routed full mesh over Thunderbolt with a Proxmox VE SDN OpenFabric fabric, verified end to end (routes, full-MTU pings) |
| ✅ | Mesh as redundant corosync link and as live migration network |
| ✅ | Certificates from the cluster CA, optionally ACME (Let's Encrypt) with automatic renewal |
| 🚧 | Ceph (Tentacle) deployment on the Thunderbolt mesh |

## 🚀 Quick start

**Requirements:** Ansible ≥ 2.19, three Proxmox VE 9 nodes reachable over SSH as root, cabled in a Thunderbolt triangle.

```bash
# 1. Install collection dependencies
ansible-galaxy collection install -r .devcontainer/requirements.yml

# 2. Create your inventory from the sample
cp -r inventory/sample inventory/mycluster
$EDITOR inventory/mycluster/inventory.ini inventory/mycluster/group_vars/all/all.yml

# 3. Deploy
ansible-playbook -i inventory/mycluster/inventory.ini setup.yml
```

Each role has a tag, so parts can be run on their own, e.g. `--tags thunderbolt` or `--tags certificates`.

The same playbook can be run from the installed collection, without a checkout:

```bash
ansible-galaxy collection install pfurtschellerp.proxspray
ansible-playbook -i inventory.ini pfurtschellerp.proxspray.setup
```

> 💡 Prefer a ready-made toolchain? Open the repo in the included **Dev Container** — Ansible, `ansible-lint` and all collections are preinstalled.

## ⚙️ Configuration

One inventory describes one cluster. Each host needs a unique `node_id` (1–3), which selects its address on the Thunderbolt fabric (`10.100.0.<node_id>`). `node_ip` (optional) is the management address; it defaults to the address of the default route.

```ini
[all]
node-1 ansible_host=10.10.1.6 node_id=1
node-2 ansible_host=10.10.1.7 node_id=2
node-3 ansible_host=10.10.1.8 node_id=3
```

The commonly changed settings are listed in [inventory/sample/group_vars/all/all.yml](inventory/sample/group_vars/all/all.yml); every variable is documented in its role's `defaults/main.yml`.

| Role | Purpose | Key variables |
| ---- | ------- | ------------- |
| [proxmox](roles/proxmox/defaults/main.yml) | Repositories, packages, `/etc/hosts`, time | `proxmox_repository`, `proxmox_ceph_release`, `proxmox_timezone`, `proxmox_ntp_servers`, `proxmox_apt_upgrade` |
| [cluster](roles/cluster/defaults/main.yml) | Create and join the cluster | `cluster_name`, `cluster_init_node`, `cluster_links` |
| [thunderbolt](roles/thunderbolt/defaults/main.yml) | Thunderbolt links | `thunderbolt_devices` (interface → port path), `thunderbolt_mtu` |
| [fabric](roles/fabric/defaults/main.yml) | Routed mesh, corosync link, migration network | `fabric_ip_prefix`, `fabric_corosync_link`, `fabric_migration_network`, `fabric_migration_type` |
| [certificates](roles/certificates/defaults/main.yml) | Web interface / API certificates | `certificates_mode`, `certificates_acme_*` |

### 🕸️ Thunderbolt fabric

The cluster is created on the management network first, because the fabric is cluster-wide SDN configuration. The `fabric` role then defines an OpenFabric fabric (`tbmesh`) with every node's router ID and its Thunderbolt interfaces, applies it, and waits until each node reaches all others over the mesh. It then adds the mesh as corosync link 1, with link 0 on the management network kept preferred, and sets the cluster's migration network. When you set up Ceph, choose the fabric network (`10.100.0.0/24`).

### 🔐 Certificates

By default (`certificates_mode: self_signed`) the nodes keep the certificates Proxmox VE issues from the cluster's own CA. The role regenerates them if they are about to expire or don't cover the node's name, and removes custom certificates. Set `certificates_fetch_ca: true` to copy `pve-root-ca.pem` to `<inventory>/artifacts/` and add it to your trust store.

With `certificates_mode: acme` the role registers an ACME account, configures DNS plugins and orders a certificate for every node using Proxmox VE's built-in client, which renews it automatically:

```yaml
certificates_mode: acme
certificates_acme_email: admin@example.com
certificates_acme_plugins:
  - id: cloudflare
    api: cf                # acme.sh DNS API name
    data:
      CF_Token: "{{ vault_cloudflare_token }}"
```

Try it against the Let's Encrypt staging directory first (`certificates_acme_directory`). Without a plugin, the HTTP challenge is used, which needs port 80 of the nodes reachable from the internet.

## 📁 Layout

```
.
├── setup.yml              # Entry point (imports playbooks/setup.yml)
├── playbooks/             # Playbooks, also available as pfurtschellerp.proxspray.<name>
├── roles/
│   ├── proxmox/           # Node essentials
│   ├── cluster/           # Cluster creation and join
│   ├── thunderbolt/       # Thunderbolt links
│   ├── fabric/            # Routed mesh (SDN OpenFabric), corosync link, migration
│   └── certificates/      # Cluster CA or ACME certificates
├── inventory/sample/      # Example inventory
├── changelogs/            # antsibull-changelog fragments and history
└── .devcontainer/         # Ready-to-use dev environment
```

## 🛠️ Development

Every change needs a changelog fragment in `changelogs/fragments/` (see the [antsibull-changelog docs](https://ansible.readthedocs.io/projects/antsibull-changelog/changelogs/)). CI runs `yamllint`, `ansible-lint`, `antsibull-changelog lint`, `ansible-test sanity` and syntax checks from a checkout and from the built collection.

To release, bump `version` in `galaxy.yml`, then:

```bash
antsibull-changelog release      # collects the fragments into CHANGELOG.md
git commit -am "chore: release X.Y.Z" && git tag vX.Y.Z && git push --follow-tags
```

The tag triggers the release workflow, which publishes to Ansible Galaxy (secret `GALAXY_API_KEY` in the `release` environment) and creates a GitHub release.

## 📄 License

[GPL-3.0](LICENSE) © Patrick Pfurtscheller
