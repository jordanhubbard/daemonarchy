# Omarchy FreeBSD integration acceptance

Acceptance binds exact input/source identities, test command, worker/OS, artifact
hash, result and limitations. Historical results are evidence only for their
recorded scope; these requirements are not a current execution receipt.

## Existing candidate checks

- [tests/enterprise-wifi-options.sh](../../tests/enterprise-wifi-options.sh)
- [tests/installed-desktop.sh](../../tests/installed-desktop.sh)

Read each command's platform and privilege requirements before execution. The
complete declarations and external/native gaps are in [the acceptance inventory](../../verification/acceptance-inventory.json).

## Required scenarios

- **Native service semantics:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Hardware capability reporting:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **External source custody:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
