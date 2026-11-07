# AGENTS.md

Conventions for working on this repository. They describe how the code is
written today; change them here when the style changes.

Generic Ansible and YAML practices are enforced by `ansible-lint` (production
profile) and `yamllint` (see [Checks](#checks)): FQCNs, task and handler
names, role-prefixed variable names, `changed_when` on commands, file modes,
modules instead of known commands, no role `meta` dependencies, YAML
formatting. This file only lists what the linters don't check.

## Project

- `pfurtschellerp.proxspray` is an Ansible collection that sets up a Proxmox VE 9
  cluster (Debian 13 "trixie") on three nodes connected by a Thunderbolt 4 mesh.
- Minimum Ansible version: 2.19 (`meta/runtime.yml`, `playbooks/ansible_version.yml`).
- One inventory describes exactly one cluster. Roles use `groups['all']` as the
  list of cluster nodes. Fleet deployments are out of scope for now.
- Hardware is not available in CI. Changes are checked with static tests and
  local logic tests, so state clearly what still needs testing on real nodes.

## Layout

- The repository follows kubespray's "collection + playbooks" approach:
  - `setup.yml` at the top level imports `playbooks/setup.yml`.
  - Playbooks in `playbooks/` refer to roles by their **short name** (`proxmox`,
    not `pfurtschellerp.proxspray.proxmox`). From a checkout they resolve through
    `roles_path` in `ansible.cfg`; from the installed collection
    (`ansible-playbook pfurtschellerp.proxspray.setup`) Ansible resolves them
    inside the collection. Both ways must keep working.
- Play order in `playbooks/setup.yml`: Ansible version check → facts of all
  nodes → `proxmox` → `cluster` → `thunderbolt` + `fabric` → `ceph` →
  `certificates`.
  Every role has a tag with its own name.
- Other top-level playbooks follow the same pattern: `install_media.yml`
  (runs on the controller, every task `delegate_to: localhost`),
  `reinstall.yml` (destructive, guarded by `reinstall_confirm`) and
  `update.yml` (rolling update: a check play, the nodes with `serial: 1`, a
  finish play, all from one role via `tasks_from`).
- Generated files go to `<inventory>/artifacts/`, generated secrets to
  `<inventory>/credentials/`; both are git-ignored and excluded from the
  collection build.
- `inventory/sample/` is the documented example; commonly changed settings are
  listed (commented out) in `inventory/sample/group_vars/all/all.yml`.

## Roles

- `defaults/main.yml` holds user-facing variables, each with a comment on what
  it does, its allowed values and, where relevant, the trade-off.
  `vars/main.yml` holds derived/internal values.
- `tasks/main.yml` only imports task files, in this order where applicable:
  `validate.yml` (no changes, fail early) → configuration task files →
  `meta: flush_handlers` → `verify.yml` (skipped in check mode, switchable
  with `<role>_verify`).
- `import_tasks` for static task files, `include_tasks` only when the file is
  chosen at runtime (e.g. by mode).
- Values shared between roles come from inventory variables (`node_id`,
  `node_ip`) or from a role in the same play (e.g. `fabric` reads
  `thunderbolt_devices`); always provide a fallback with `default(...)`.

### Variables

- Loop variables are role-prefixed too: set `loop_control.loop_var` (never the
  implicit `item`) and a short `label`.
- Read facts as `ansible_facts.<name>`, never as injected `ansible_<name>`
  variables.
- Role defaults are not part of `hostvars`; to read another host's value,
  compute it from inventory variables or `set_fact` it on that host first.

### Tasks

- Prefer modules over commands even where ansible-lint can't tell (e.g.
  `ansible.builtin.getent`, `ansible.builtin.slurp` instead of `cat`,
  `ansible.builtin.user` for SSH keys).
- For Proxmox VE, use `community.proxmox` modules where they fit, **without**
  `api_host`: they then use the local API backend on the node (as root, no
  credentials) and need `python3-proxmoxer` on the node. Fall back to `pvesh`,
  `pvecm` or `pvenode` with `ansible.builtin.command` when there is no module
  or the module needs credentials (e.g. `proxmox_cluster` joins with the root
  password; the cluster role joins over SSH instead). Current CLI uses: cluster
  status/create/join, SDN fabrics, cluster options, node certificate cleanup,
  ACME terms of service. If there is no suitable module, propose to write one
  that can be contributed to the community.
- When the same logic is needed by Ansible and by the node itself (e.g. an
  APT hook), install it as a script and call that script from both.
- `command` with user-provided values uses `argv`; `shell` scripts start with
  `set -eu`.
- Commands are idempotent:
  - read-only commands also set `check_mode: false`, so they run in check mode;
  - changing commands only run when a `when` on the observed state says
    something has to change (`changed_when: true` then), or report their own
    result (e.g. a script that prints `changed`).
- Cluster-wide changes (data in `/etc/pve`) run once with `run_once: true`.
  Only the first host evaluates the conditions of a `run_once` task, so they
  must be the same on every host. Never put `run_once` inside a block whose
  condition differs between hosts.
- Operations that must not run concurrently (joining nodes, ordering
  certificates) use `throttle: 1`.
- Long-running state changes are followed by a wait with
  `until`/`retries`/`delay`, with retries derived from a `<role>_*_timeout`
  variable.
- `no_log: true` on tasks that handle secrets.
- Files on the nodes also set `owner` and `group`. Prefer drop-in files
  (`/etc/sysctl.d`, `/etc/network/interfaces.d`,
  `/etc/apt/sources.list.d/*.sources`, `/etc/chrony/sources.d`) over editing
  files that Proxmox VE or the distribution own.
- Comments explain *why* something is done when it is not obvious (Proxmox or
  Debian behaviour, ordering constraints), not what a task does.

### Validation and verification

- Validate input with `ansible.builtin.assert` before changing anything:
  `quiet: true` and a `fail_msg` that says what is wrong, what was found and
  how to fix it.
- Verify the result at the end of a role (interfaces up, routes, pings, quorum)
  and fail with a message that points to the next debugging step.

### Handlers and templates

- Handlers run in the order they are defined in `handlers/main.yml`; order them
  by dependency (rename interfaces → initramfs → systemd → udev → network).
- Templates start with `{{ ansible_managed | comment }}` (with the matching
  comment style, e.g. `comment('c')`) and use `dictsort`/`sort` for stable
  output.
- Long Jinja expressions go into `>-` blocks, one operator per line.

## Changelog

- Every change gets a fragment in `changelogs/fragments/<topic>.yml`
  ([antsibull-changelog](https://ansible.readthedocs.io/projects/antsibull-changelog/changelogs/)).
- Entries start with the affected role or file (`thunderbolt - ...`), are full
  sentences and wrap code in double backticks.
- Sections: `major_changes` for new roles, `minor_changes` for new options,
  `bugfixes`, `breaking_changes`; use `trivial` for CI and tooling.
- Nothing has been released yet, so fragments describe features, not fixes to
  unreleased code.

## Checks

Run before considering a change done (`just check` runs them all):

```bash
ansible-lint                     # production profile
yamllint .
antsibull-changelog lint
ansible-playbook -i inventory/sample/inventory.ini --syntax-check \
  setup.yml install_media.yml reinstall.yml update.yml
```

`ansible-test sanity` needs the collection at
`ansible_collections/pfurtschellerp/proxspray/`; CI runs it on every supported
ansible-core version. It checks every tracked file, including
`.devcontainer/` scripts and `roles/*/files/` (e.g. the shebang has to be
`#!/usr/bin/env python`). Without the `shellcheck` binary a local run skips
that test with only a warning, so install it (e.g. `pip install shellcheck-py`)
before relying on a local result.

Template logic is tested locally by running the role's expressions against
`localhost` with mocked command output; there are no Molecule tests because
Proxmox VE cannot run in a container.

## Git

- Conventional commits with the role as scope, e.g. `feat(fabric): ...`,
  `fix(thunderbolt): ...`, `docs: ...`, `refactor(devcontainer): ...`.
- Only commit when asked.
