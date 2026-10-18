#!/usr/local/bin/bash
# One-time opt-in after selecting a versioned Daemonarchy candidate feed.
set -euo pipefail

candidate_base_error() {
  printf 'Candidate adoption refused: %s. Upgrade the FreeBSD base and kernel together, with matching drivers, before selecting this feed. No package identities were changed.\n' "$1" >&2
  return 1
}

candidate_adopt_installed_packages() {
  local names package repository kernel userland catalog annotations abi tag version extra required=0
  local -a pkg_command=("$@") selected=()
  local -A package_abi=() package_version=()
  # uname supports UNAME_K/UNAME_U overrides. Read the actual running kernel
  # and installed user environment, independently of pkg's override settings.
  kernel=$(/usr/bin/env -u UNAME_K /usr/bin/uname -K) || { candidate_base_error 'cannot determine the kernel version'; return 1; }
  userland=$(/usr/bin/env -u UNAME_U /usr/bin/uname -U) || { candidate_base_error 'cannot determine the userland version'; return 1; }
  [[ $kernel =~ ^[1-9][0-9]{6,8}$ && $userland =~ ^[1-9][0-9]{6,8}$ ]] || {
    candidate_base_error 'invalid kernel or userland version'; return 1;
  }
  # Permit only catalogue inspection across an OS mismatch. pkg install -y
  # itself accepts newer-OS packages, so its interactive warning is no guard.
  "${pkg_command[@]}" -o IGNORE_OSVERSION=yes update -f -r Daemonarchy || {
    candidate_base_error 'cannot refresh the candidate catalogue'; return 1;
  }
  catalog=$("${pkg_command[@]}" rquery -U -r Daemonarchy '%n|%q') || {
    candidate_base_error 'cannot read the candidate catalogue'; return 1;
  }
  [[ -n $catalog ]] || { candidate_base_error 'empty candidate catalogue'; return 1; }
  names=''
  while IFS='|' read -r package abi extra; do
    [[ $package =~ ^[A-Za-z0-9][A-Za-z0-9+_.-]*$ && -z $extra &&
       ( $abi == FreeBSD:16:amd64 || $abi == 'FreeBSD:16:*' ) &&
       ! -v package_abi[$package] ]] || {
      candidate_base_error 'invalid candidate package identity or ABI'; return 1;
    }
    package_abi[$package]=$abi
    names+="$package"$'\n'
  done <<<"$catalog"
  annotations=$("${pkg_command[@]}" rquery -U -r Daemonarchy '%n|%At|%Av') || {
    candidate_base_error 'cannot read candidate OS requirements'; return 1;
  }
  while IFS='|' read -r package tag version extra; do
    [[ -n $package ]] || continue
    [[ $package =~ ^[A-Za-z0-9][A-Za-z0-9+_.-]*$ && -v package_abi[$package] ]] || {
      candidate_base_error 'unknown annotated package'; return 1;
    }
    [[ $tag == FreeBSD_version ]] || continue
    [[ $version =~ ^[1-9][0-9]{6,8}$ && -z $extra && ! -v package_version[$package] ]] || {
      candidate_base_error "invalid OS requirement for $package"; return 1;
    }
    package_version[$package]=$version
    (( 10#$version <= required )) || required=$((10#$version))
  done <<<"$annotations"
  for package in "${!package_abi[@]}"; do
    [[ ${package_abi[$package]} == 'FreeBSD:16:*' || -v package_version[$package] ]] || {
      candidate_base_error "missing OS requirement for $package"; return 1;
    }
  done
  if (( 10#$kernel < required || 10#$userland < required )); then
    candidate_base_error "feed requires OSVERSION $required; kernel is $kernel and userland is $userland"; return 1
  fi
  "${pkg_command[@]}" update -f || { candidate_base_error 'cannot refresh package catalogues'; return 1; }
  while IFS= read -r package; do
    [[ -n $package ]] || continue
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
