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
| ✅ | Unattended installation: per-node installer ISOs generated from the inventory, reinstall from a plugged-in USB stick with a one-time UEFI boot |
| ✅ | Rolling updates: health checks, guests moved away (HA maintenance mode, live and restart migration) and back, Ceph `noout`, reboot only when needed |
| ✅ | Proxmox VE essentials: deb822 repositories (enterprise / no-subscription / test), packages, `/etc/hosts`, timezone, NTP |
| ✅ | Thunderbolt links: `thunderbolt-net` modules, stable `en05`/`en06` naming via systemd `.link` files, MTU, hotplug and boot-time bringup |
| ✅ | Proxmox VE cluster creation and node join (over SSH, no root password needed) |
| ✅ | Routed full mesh over Thunderbolt with a Proxmox VE SDN OpenFabric fabric, verified end to end (routes, full-MTU pings) |
| ✅ | Mesh as redundant corosync link and as live migration network |
| ✅ | Certificates from the cluster CA, optionally ACME (Let's Encrypt) with automatic renewal |
| ✅ | Ceph (Tentacle) on the Thunderbolt mesh: RBD pool for VM disks, CephFS with an erasure-coded media directory |

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

> 💡 Prefer a ready-made toolchain? Open the repo in the included **Dev Container** — Ansible, `ansible-lint`, all collections, `just` and the GitHub CLI are preinstalled. Run `gh auth login` to use it; the login is lost when the container is rebuilt.

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
| [install_media](roles/install_media/defaults/main.yml) | Unattended installer ISO per node (runs on the controller) | `install_media_domain`, `install_media_gateway`, `install_media_dns`, `install_media_disk_list`, `install_media_root_password_hash`, `install_media_root_ssh_keys` |
| [reinstall](roles/reinstall/defaults/main.yml) | Reinstall nodes from their plugged-in stick | `reinstall_confirm`, `reinstall_update_media`, `reinstall_destroy_guests` |
| [proxmox](roles/proxmox/defaults/main.yml) | Repositories, packages, `/etc/hosts`, time | `proxmox_repository`, `proxmox_ceph_release`, `proxmox_timezone`, `proxmox_ntp_servers`, `proxmox_apt_upgrade` |
| [cluster](roles/cluster/defaults/main.yml) | Create and join the cluster | `cluster_name`, `cluster_init_node`, `cluster_links` |
| [thunderbolt](roles/thunderbolt/defaults/main.yml) | Thunderbolt links | `thunderbolt_devices` (interface → port path), `thunderbolt_mtu` |
| [fabric](roles/fabric/defaults/main.yml) | Routed mesh, corosync link, migration network | `fabric_ip_prefix`, `fabric_corosync_link`, `fabric_migration_network`, `fabric_migration_type` |
| [ceph](roles/ceph/defaults/main.yml) | Ceph monitors, managers, metadata servers, OSDs, pools, CephFS | `ceph_osd_devices`, `ceph_osd_model`, `ceph_media_*`, `ceph_osd_memory_target` |
| [update](roles/update/defaults/main.yml) | Rolling update of all nodes (`update.yml`) | `update_reboot`, `update_migrate`, `update_memory_reserve` |
| [certificates](roles/certificates/defaults/main.yml) | Web interface / API certificates | `certificates_mode`, `certificates_acme_*` |

### 💿 Installing the nodes

No PXE and no DHCP changes: every node gets its own USB stick with an installer ISO built from the inventory (Proxmox VE [automated installation](https://pve.proxmox.com/wiki/Automated_Installation)). The ISO holds the node's FQDN, static address, target disk, root password hash and SSH keys and installs without a single keypress.

```bash
# 1. Build inventory/<cluster>/artifacts/install-media/<node>.iso for every node
ansible-playbook -i inventory/mycluster/inventory.ini install_media.yml

# 2. First installation: write each ISO to a stick, plug it in and pick it once in the boot menu
sudo dd if=inventory/mycluster/artifacts/install-media/node-1.iso of=/dev/sdX bs=4M conv=fsync oflag=direct status=progress

# 3. Configure the cluster
ansible-playbook -i inventory/mycluster/inventory.ini setup.yml
```

Leave the sticks plugged in. Later reinstalls need no hands on the machines: `reinstall.yml` checks the stick, rewrites it if the ISO changed, adds a UEFI boot entry for it that is *not* in the boot order, selects it once with `BootNext` and reboots. The installer reboots into the new system, and the playbook waits for it:

```bash
ansible-playbook -i inventory/mycluster/inventory.ini reinstall.yml setup.yml -e reinstall_confirm=node-1,node-2,node-3
```

- **SSH host keys stay the same.** `install_media` takes the keys of the running nodes (or generates them) into `inventory/<cluster>/credentials/`, a first-boot hook restores them before sshd starts, and they are added to your `known_hosts`. Neither Ansible nor the other cluster nodes see a changed host key.
- **Other disks:** the installer only touches its target disks. With `install_media_wipe_disks: true` the first boot also wipes every other disk except USB devices (partition tables and LVM, Ceph or ZFS signatures), e.g. to reuse a Ceph disk; it finds the system disks by what the new system uses, not by name.
- **Network:** `install_media_interface_filter` selects the management port by udev properties, e.g. `{ID_NET_NAME_PATH: enp86s0}` once for identical machines, or by MAC with `node_mac` per host.
- **Single nodes** can be reinstalled with `--limit`; the remaining nodes must keep quorum, and the old node is removed from the cluster before `setup.yml` joins it again. With Ceph, all PGs must be `active+clean` first and `install_media_wipe_disks` must be on; the remaining nodes forget the old monitor, OSDs and daemon keys, and Ceph rebuilds the data on the new OSD.
- **Safeguards:** `reinstall_confirm` must list exactly the selected nodes, nodes with guests are refused (`reinstall_destroy_guests`), and the firmware must boot the system disk first so the stick never boots by accident.
- **Tools:** `proxmox-auto-install-assistant` and `xorriso` are in the Dev Container; elsewhere install them from the Proxmox VE repository. The ISOs and `credentials/` contain secrets and are git-ignored.

### 🕸️ Thunderbolt fabric

The cluster is created on the management network first, because the fabric is cluster-wide SDN configuration. The `fabric` role then defines an OpenFabric fabric (`tbmesh`) with every node's router ID and its Thunderbolt interfaces, applies it, and waits until each node reaches all others over the mesh. It then adds the mesh as corosync link 1, with link 0 on the management network kept preferred, and sets the cluster's migration network. When you set up Ceph, choose the fabric network (`10.100.0.0/24`).

### 🐙 Ceph

Ceph runs hyper-converged on the three nodes, entirely on the Thunderbolt fabric (`10.100.0.0/24`), and is managed like any Proxmox VE Ceph cluster in the web interface. Every node runs a monitor, a manager and a metadata server. Every empty disk that is not a USB device becomes an OSD (`ceph_osd_devices: auto`, optionally narrowed by a model pattern in `ceph_osd_model`); disks with partitions or data, like the system disk, are never used. No disk IDs are needed in the inventory.

| Storage | Ceph | For |
| ------- | ---- | --- |
| `vm` (RBD) | pool `vm`, 3 replicas, `min_size` 2 | VM disks and container volumes; a node can fail without stopping them |
| `cephfs` (`/mnt/pve/cephfs`) | `cephfs_data`, 3 replicas | ISO images, templates, backups, snippets |
| `/mnt/pve/cephfs/media` | `cephfs_media`, erasure coded 2+1 | Movies, series and other large files, at 1.5× instead of 3× the raw space |

The media directory survives one failed node like the replicated pools. With `ceph_media_min_size: 2` (default) it stays writable while a node is down, e.g. during updates; data written meanwhile has no redundancy until the node is back. `3`, Ceph's recommendation, blocks media I/O whenever a node is down instead. Bind-mount the directory into containers (e.g. `mp0: /mnt/pve/cephfs/media,mp=/media`).

On nodes with little memory, OSD memory (`ceph_osd_memory_target`, 3 GiB) and the metadata server cache (`ceph_mds_cache_memory_limit`, 1 GiB) are below Ceph's defaults of 4 GiB each.

### 🔄 Updating the cluster

```bash
ansible-playbook -i inventory/mycluster/inventory.ini update.yml --check   # show the plan
ansible-playbook -i inventory/mycluster/inventory.ini update.yml
```

`update.yml` first checks the whole cluster: quorum, all nodes online, Ceph healthy with all PGs `active+clean`, no running backup or replication, no HA errors. It also finds out which nodes have pending upgrades or run an older kernel than the installed one; nodes with nothing to do are skipped (`update_force: true` updates them anyway). Then it updates one node at a time:

1. Wait until the cluster is healthy.
2. Enable HA maintenance mode, which moves HA guests away; live-migrate the other running VMs (local disks included) and restart-migrate containers to the nodes with the most free memory, after checking that they fit.
3. Set Ceph `noout`, run `apt full-upgrade`, reboot if a new kernel is installed or a reboot is requested (`update_reboot`), and check that the new kernel runs.
4. Wait for quorum, all nodes online and Ceph recovered, end maintenance mode (HA moves its guests back) and migrate the other guests back.

Finally it clears `noout`. Any failure stops the run before the next node: the node stays in maintenance mode and Ceph keeps `noout`, so nothing moves back onto a broken node. Fix the cause and run `update.yml` again; it continues where it stopped.

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
├── install_media.yml      # Build the per-node installer ISOs
├── reinstall.yml          # Reinstall nodes from their plugged-in stick
├── update.yml             # Rolling update of all nodes
├── playbooks/             # Playbooks, also available as pfurtschellerp.proxspray.<name>
├── roles/
│   ├── install_media/     # Unattended installer ISOs (controller)
│   ├── reinstall/         # One-time UEFI boot into the installer stick
│   ├── proxmox/           # Node essentials
│   ├── cluster/           # Cluster creation and join
│   ├── thunderbolt/       # Thunderbolt links
│   ├── fabric/            # Routed mesh (SDN OpenFabric), corosync link, migration
│   ├── ceph/              # Ceph: VM pool, CephFS, erasure-coded media directory
│   ├── update/            # Rolling update with migration and maintenance flags
│   └── certificates/      # Cluster CA or ACME certificates
├── inventory/sample/      # Example inventory
├── changelogs/            # antsibull-changelog fragments and history
└── .devcontainer/         # Ready-to-use dev environment
```

## 🛠️ Development

Every change needs a changelog fragment in `changelogs/fragments/` (see the [antsibull-changelog docs](https://ansible.readthedocs.io/projects/antsibull-changelog/changelogs/)). CI runs `yamllint`, `ansible-lint`, `antsibull-changelog lint`, `ansible-test sanity` and syntax checks from a checkout and from the built collection.

`just check` runs the same checks locally.

Releasing takes two steps on an up-to-date `main` ([scripts/release.sh](scripts/release.sh)):

```bash
just release-prepare 1.1.0 "Optional summary shown at the top of the release notes"
# → branch release/v1.1.0: version set in galaxy.yml, all fragments collected into
#   changelogs/changelog.yaml and CHANGELOG.md and deleted, pushed. Open the PR and merge it.

git switch main && git pull
just release-tag
# → tags v1.1.0 and pushes the tag
```

The tag triggers the release workflow, which checks that it matches `galaxy.yml`, takes the release notes from `changelogs/changelog.yaml`, publishes to Ansible Galaxy (secret `GALAXY_API_KEY` in the `release` environment) and creates a GitHub release. Release pull requests (`release/*`) need no changelog fragment.
