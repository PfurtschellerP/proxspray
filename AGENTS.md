# AGENTS.md

Conventions for working on this repository. They describe how the code is
written today; change them here when the style changes.

## Project

- `pfurtschellerp.proxspray` is an Ansible collection that sets up a Proxmox VE 9
  cluster (Debian 13 "trixie") on three nodes connected by a Thunderbolt 4 mesh.
- Minimum Ansible version: 2.19 (`meta/runtime.yml`, `playbooks/ansible_version.yml`).
- One inventory describes exactly one cluster. Roles use `groups['all']` as the
  list of cluster nodes. Fleet deployments are out of scope for now.
- Hardware is not available in CI. Changes are checked with static tests and
  local logic tests (see [Checks](#checks)), so state clearly what still needs
  testing on real nodes.

## Layout

- The repository follows kubespray's "collection + playbooks" approach:
  - `setup.yml` at the top level imports `playbooks/setup.yml`.
  - Playbooks in `playbooks/` refer to roles by their **short name** (`proxmox`,
    not `pfurtschellerp.proxspray.proxmox`). From a checkout they resolve through
    `roles_path` in `ansible.cfg`; from the installed collection
    (`ansible-playbook pfurtschellerp.proxspray.setup`) Ansible resolves them
    inside the collection. Both ways must keep working.
- Play order in `playbooks/setup.yml`: Ansible version check → facts of all
  nodes → `proxmox` → `cluster` → `thunderbolt` + `fabric` → `certificates`.
  Every role has a tag with its own name.
- `inventory/sample/` is the documented example; commonly changed settings are
  listed (commented out) in `inventory/sample/group_vars/all/all.yml`.

## Roles

- Structure: `defaults/main.yml` (user-facing variables), `vars/main.yml`
  (derived/internal values), `tasks/main.yml` that only imports task files,
  `handlers/main.yml`, `templates/`, `files/`, `meta/main.yml`.
- `tasks/main.yml` imports, in this order where applicable: `validate.yml`
  (no changes, fail early) → configuration task files → `meta: flush_handlers`
  → `verify.yml` (skipped in check mode and switchable with `<role>_verify`).
- Use `ansible.builtin.import_tasks` for static task files and
  `ansible.builtin.include_tasks` only when the file is chosen at runtime
  (e.g. by mode).
- Every role is self-contained and has no `meta` dependencies. Values shared
  between roles come from inventory variables (`node_id`, `node_ip`) or from a
  role in the same play (e.g. `fabric` reads `thunderbolt_devices`); always
  provide a fallback with `default(...)`.

### Variables

- Every variable a role defines (defaults, vars, `set_fact`, `register`,
  `loop_var`) starts with the role name and an underscore (`thunderbolt_mtu`,
  `cluster_status`). Never use the implicit `item`; set `loop_control.loop_var`
  and a short `label`.
- Every default has a comment that explains what it does, its allowed values
  and, where relevant, the trade-off.
- Read facts as `ansible_facts.<name>`, never as injected `ansible_<name>`
  variables.
- Variables of other hosts are read through `hostvars[...]`; role defaults are
  not part of `hostvars`, so compute per-host values from inventory variables or
  `set_fact` them.

### Tasks

- Use FQCNs for everything (`ansible.builtin.template`, `community.general.modprobe`).
- Every task has a name in the imperative, starting with a capital letter, with
  Jinja only at the end of the name.
- Prefer a module over `command`/`shell` whenever one exists (e.g.
  `ansible.builtin.getent`, `ansible.builtin.slurp` instead of `cat`,
  `ansible.builtin.user` for SSH keys).
- For Proxmox VE, use `community.proxmox` modules where they fit, **without**
  `api_host`: they then use the local API backend on the node (as root, no
  credentials) and need `python3-proxmoxer` on the node. Fall back to `pvesh`,
  `pvecm` or `pvenode` with `ansible.builtin.command` when there is no module
  or the module needs credentials (e.g. `proxmox_cluster` joins with the root
  password; the cluster role joins over SSH instead). Current CLI uses: cluster
  status/create/join, SDN fabrics, cluster options, node certificate cleanup,
  ACME terms of service. If there is no suitable module, propose to write one that can be contributed to the community.
- When the same logic is needed by Ansible and by the node itself (e.g. an
  APT hook), install it as a script and call that script from both, instead of
  duplicating it.
- `command` with user-provided values uses `argv`, not a string.
- `shell` is only for pipes, globs, loops or redirects; start the script with
  `set -eu`.
- Every `command`/`shell`/`script` task sets `changed_when`:
  - read-only commands: `changed_when: false` and `check_mode: false`;
  - changing commands: guarded by a `when` on the observed state, so they only
    run when something has to change, and report `changed_when: true` (or
    parse the output, e.g. a script that prints `changed`).
- A task whose only condition is `when: x is changed` should be a handler (ansible-lint `no-handler`); otherwise use a
  condition on the observed state (`is not skipped`, comparisons).
- Cluster-wide changes (data in `/etc/pve`) run once with `run_once: true`.
  The conditions of a `run_once` task must be the same on every host, because
  only the first host evaluates them. Never put `run_once` inside a block whose
  condition differs between hosts.
- Operations that must not run concurrently (joining nodes, ordering
  certificates) use `throttle: 1`.
- Long-running state changes are followed by a wait with
  `until`/`retries`/`delay`, with retries derived from a `<role>_*_timeout`
  variable.
- Secrets never show up in logs: `no_log: true` on tasks that handle them.
- Files written to the nodes set `owner`, `group` and a quoted `mode`
  (`"0644"`). Prefer drop-in files (`/etc/sysctl.d`, `/etc/network/interfaces.d`,
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

### Handlers

- Handlers run in the order they are defined in `handlers/main.yml`; order them
  by dependency (rename interfaces → initramfs → systemd → udev → network).
- Handler names are capitalised imperatives (`Reload network interfaces`).

### Templates

- Start with `{{ ansible_managed | comment }}` (use the matching comment style,
  e.g. `comment('c')`).
- Use `dictsort`/`sort` for stable output.

## YAML style

- Start every file with `---`, indent with 2 spaces, lists indented under
  their key.
- Double quotes for strings that contain Jinja; `>-` for long expressions,
  one operator per line.
- Max. line length 160 (`.yamllint`).
- Booleans are `true`/`false`.

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

Run before considering a change done:

```bash
ansible-lint                     # production profile
yamllint .
antsibull-changelog lint
ansible-playbook -i inventory/sample/inventory.ini setup.yml --syntax-check
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
