#!/usr/bin/env bash
# Releases the collection in two steps (see README, "Releasing"):
#
#   scripts/release.sh prepare <X.Y.Z> [summary]
#       From an up-to-date main: creates the branch release/v<X.Y.Z>, sets the
#       version in galaxy.yml, collects the changelog fragments into
#       changelogs/changelog.yaml and CHANGELOG.md (the fragments are deleted),
#       commits and pushes the branch. Open and merge the pull request.
#
#   scripts/release.sh tag [--yes]
#       From main after the merge: tags v<version from galaxy.yml> and pushes
#       the tag, which makes the release workflow publish the collection.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

die() {
    echo "error: $*" >&2
    exit 1
}

info() {
    echo "==> $*"
}

galaxy_version() {
    python3 -c 'import yaml; print(yaml.safe_load(open("galaxy.yml"))["version"])'
}

is_released() {
    python3 - "$1" <<'EOF'
import sys, yaml
releases = yaml.safe_load(open("changelogs/changelog.yaml")).get("releases") or {}
sys.exit(0 if sys.argv[1] in releases else 1)
EOF
}

repo_url() {
    git remote get-url origin | sed -E 's#^git@([^:]+):#https://\1/#; s#\.git$##'
}

require_clean_main() {
    [ "$(git branch --show-current)" = main ] || die "switch to main first (git switch main)"
    [ -z "$(git status --porcelain)" ] || die "the working tree is not clean"
    git fetch --quiet origin main
    [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] ||
        die "main differs from origin/main; run git pull first"
}

prepare() {
    local version=${1:-} summary=${2:-}
    [[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "usage: $0 prepare <X.Y.Z> [summary]"
    require_clean_main
    command -v antsibull-changelog >/dev/null || die "antsibull-changelog not found (it is in the Dev Container)"
    ! git rev-parse --quiet --verify "refs/tags/v$version" >/dev/null || die "tag v$version already exists"
    ! is_released "$version" || die "$version is already in changelogs/changelog.yaml"
    compgen -G 'changelogs/fragments/*.yml' >/dev/null || [ -n "$summary" ] ||
        die "no changelog fragments since the last release, nothing to release"

    local branch="release/v$version"
    info "Creating branch $branch"
    git switch --create "$branch"

    info "Setting version $version in galaxy.yml"
    sed -i -E "s/^version: .*/version: $version/" galaxy.yml

    if [ -n "$summary" ]; then
        info "Adding the release summary"
        python3 - "$summary" "changelogs/fragments/v$version-summary.yml" <<'EOF'
import sys, yaml
with open(sys.argv[2], "w") as f:
    f.write("---\n")
    yaml.safe_dump({"release_summary": sys.argv[1]}, f, allow_unicode=True, width=1000)
EOF
    fi

    info "Collecting the changelog fragments"
    antsibull-changelog lint
    antsibull-changelog release

    git add --all galaxy.yml changelogs CHANGELOG.md
    git commit --quiet --message "chore: release $version"
    info "Committed:"
    git show --stat --format='    %s' HEAD | tail -n +2

    info "Pushing $branch"
    git push --set-upstream origin "$branch"

    cat <<EOF

Next steps:
  1. Open the pull request and merge it once the checks pass:
     $(repo_url)/compare/main...$branch?expand=1
  2. Back on main, publish the release:
     git switch main && git pull && just release-tag
EOF
}

tag() {
    local yes=${1:-}
    require_clean_main
    local version
    version=$(galaxy_version)
    ! git rev-parse --quiet --verify "refs/tags/v$version" >/dev/null ||
        die "v$version is already tagged; prepare a new release first"
    is_released "$version" ||
        die "$version is not in changelogs/changelog.yaml; merge the release pull request first"

    if [ "$yes" != "--yes" ]; then
        read -r -p "Tag v$version and publish it to Ansible Galaxy? [y/N] " answer
        [[ $answer =~ ^[Yy]$ ]] || die "aborted"
    fi

    git tag --annotate "v$version" --message "Release $version"
    git push origin "v$version"
    echo
    echo "Tagged v$version. Follow the release workflow at $(repo_url)/actions/workflows/release.yml"
}

case ${1:-} in
    prepare) shift; prepare "$@" ;;
    tag) shift; tag "$@" ;;
    *) die "usage: $0 prepare <X.Y.Z> [summary] | $0 tag [--yes]" ;;
esac
