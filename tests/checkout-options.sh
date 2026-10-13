#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/checkout-options"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cat >"$work/catalog" <<'EOF'
{"trees":{"ports":{"depth":1,"required_bytes":4000000000,"parts":[{}]},"src":{"depth":1,"required_bytes":6000000000,"parts":[{}]}}}
EOF
install_ports=false install_src=false
checkout_options_prepare "$work/absent"
[[ $MIN_INSTALL_BYTES == 21474836480 ]]
install_ports=true
checkout_options_prepare "$work/catalog"
[[ $MIN_INSTALL_BYTES == 25474836480 ]]
install_src=true
checkout_options_prepare "$work/catalog"
[[ $MIN_INSTALL_BYTES == 31474836480 ]]
if checkout_options_prepare "$work/absent"; then exit 1; fi
install_ports=bad
if checkout_options_prepare "$work/catalog"; then exit 1; fi
echo 'PASS: checkout selection defaults, independent and combined capacity, missing catalogue and invalid flags'
