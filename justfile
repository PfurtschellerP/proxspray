# Common tasks; run `just` to list them.

# List the recipes
default:
    @just --list

# Run the checks from AGENTS.md
check:
    ansible-lint
    yamllint .
    antsibull-changelog lint
    ansible-playbook -i inventory/sample/inventory.ini setup.yml install_media.yml reinstall.yml update.yml --syntax-check

# Create release/v<version> with the collected changelog and push it (summary: optional intro for the release notes)
release-prepare version summary="":
    scripts/release.sh prepare {{ quote(version) }} {{ quote(summary) }}

# Tag the merged release on main, which publishes it to Ansible Galaxy
release-tag:
    scripts/release.sh tag
