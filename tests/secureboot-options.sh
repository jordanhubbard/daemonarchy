#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/secureboot-options"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
ISO_SHARE=$work
fixture_method=UEFI fixture_state=1 fixture_byte=1
sysctl() { printf '%s\n' "$fixture_method"; }
kenv() { [[ -n $fixture_state ]] && printf '%s\n' "$fixture_state"; }
efivar() { printf '%b' "$fixture_byte"; }
[[ $(secureboot_detect_enforcement) == true ]]
fixture_state=0
[[ $(secureboot_detect_enforcement) == false ]]
fixture_state='' fixture_byte='\001'
[[ $(secureboot_detect_enforcement) == true ]]
fixture_byte='\000'
[[ $(secureboot_detect_enforcement) == false ]]
fixture_byte='\002'
if secureboot_detect_enforcement; then
  echo 'FAIL: accepted an unknown firmware state' >&2; exit 1
fi
# Firmware without the variable (plain OVMF.fd): Secure Boot is off, and the
# installer says so. This holds with and without pipefail.
efivar() { return 1; }
[[ $(secureboot_detect_enforcement 2>"$work/err") == false ]]
grep -q 'no SecureBoot variable; treating Secure Boot as off' "$work/err"
[[ $(set +o pipefail; secureboot_detect_enforcement 2>/dev/null) == false ]]
fixture_state=''
secureboot_payload_prepare 2>/dev/null
[[ $secureboot_enforced == false && $efi_pool_selector == false ]]
# A variable that exists but reads empty is still refused.
efivar() { :; }
if secureboot_detect_enforcement 2>/dev/null; then
  echo 'FAIL: accepted an empty firmware SecureBoot variable' >&2; exit 1
fi
efivar() { printf '%b' "$fixture_byte"; }
fixture_state=1
if secureboot_payload_prepare; then
  echo 'FAIL: accepted enforced boot without its signed payload' >&2; exit 1
fi
fixture_state=0
secureboot_payload_prepare
[[ $efi_pool_selector == false ]]
fixture_method=BIOS fixture_state=1
secureboot_payload_prepare
[[ $secureboot_enforced == false && $efi_pool_selector == false ]]
echo 'PASS: firmware detection (missing variable is off) and payload admission fail before disk writes'
