#!/usr/local/bin/bash
# One-time opt-in after selecting a versioned Daemonarchy candidate feed.
set -euo pipefail

candidate_adopt_installed_packages() {
  local names package repository
  local -a pkg_command=("$@") selected=()
  "${pkg_command[@]}" update -f || return 1
  names=$("${pkg_command[@]}" rquery -U -r Daemonarchy '%n') || return 1
  while IFS= read -r package; do
    [[ $package =~ ^[A-Za-z0-9][A-Za-z0-9+_.-]*$ ]] || return 1
    "${pkg_command[@]}" info -e "$package" >/dev/null 2>&1 || continue
    repository=$("${pkg_command[@]}" query '%R' "$package") || return 1
    case "$repository" in
      FreeBSD|FreeBSD-ports|Daemonarchy|Daemonarchy-ISO|Daemonarchy-Dependencies) selected+=("$package") ;;
    esac
  done <<<"$names"
  [[ ${#selected[@]} -gt 0 ]] || { echo 'No installed packages belong to this candidate feed' >&2; return 1; }
  # Adopt the selected update identities before resolving the transaction.
  # Restricting pkg install with -r also hides official-only dependencies;
  # keeping the normal resolver preserves repository affinity for overrides.
  for package in "${selected[@]}"; do
    "${pkg_command[@]}" annotate -y -M "$package" repository Daemonarchy || return 1
  done
  "${pkg_command[@]}" install -f -y "${selected[@]}"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  [[ $(uname -s) == FreeBSD && $(id -u) == 0 ]] || { echo 'Run as root on FreeBSD' >&2; exit 1; }
  grep -Eq 'url:[[:space:]]*"https://github[.]com/jordanhubbard/daemonarchy/releases/download/packages-16-amd64-[A-Za-z0-9._-]+"' \
    /usr/local/etc/pkg/repos/Daemonarchy.conf || { echo 'Select a versioned candidate feed first' >&2; exit 1; }
  candidate_adopt_installed_packages pkg
fi
