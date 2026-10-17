#!/usr/local/bin/bash
# One-time opt-in after selecting a versioned Daemonarchy candidate feed.
set -euo pipefail

candidate_adopt_installed_packages() {
  local names package repository
  local -a pkg_command=("$@") selected=()
  "${pkg_command[@]}" update -f -r Daemonarchy
  names=$("${pkg_command[@]}" rquery -U -r Daemonarchy '%n')
  while IFS= read -r package; do
    [[ $package =~ ^[A-Za-z0-9][A-Za-z0-9+_.-]*$ ]] || return 1
    "${pkg_command[@]}" info -e "$package" >/dev/null 2>&1 || continue
    repository=$("${pkg_command[@]}" query '%R' "$package")
    case "$repository" in
      FreeBSD|FreeBSD-ports|Daemonarchy|Daemonarchy-ISO|Daemonarchy-Dependencies) selected+=("$package") ;;
    esac
  done <<<"$names"
  [[ ${#selected[@]} -gt 0 ]] || { echo 'No installed packages belong to this candidate feed' >&2; return 1; }
  "${pkg_command[@]}" install -f -y -r Daemonarchy "${selected[@]}"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  [[ $(uname -s) == FreeBSD && $(id -u) == 0 ]] || { echo 'Run as root on FreeBSD' >&2; exit 1; }
  grep -Eq 'url:[[:space:]]*"https://github[.]com/jordanhubbard/daemonarchy/releases/download/packages-16-amd64-[A-Za-z0-9._-]+"' \
    /usr/local/etc/pkg/repos/Daemonarchy.conf || { echo 'Select a versioned candidate feed first' >&2; exit 1; }
  candidate_adopt_installed_packages pkg
fi
