# Secure Boot development

This directory contains work toward the 1.1 manual-enrollment boot path. It is
not an installer option yet. No release signing key or firmware-enrollment
operation belongs in this directory. See
[the evidence record](../docs/testing-1.1-secureboot.md) for qualification limits.

`patches/module-policy.patch` applies to FreeBSD source revision
`3ceb5f150bc121f5e6a3e0cc8b289279338405a1`. It adds the opt-in kernel option
`DAEMONARCHY_MODULE_POLICY`, used together with `MAC_VERIEXEC`,
`MAC_VERIEXEC_SHA256` and the `mac_veriexec_parser` device in a GENERIC-derived
kernel. Build this from a separate source worktree; do not change the builder's
running kernel or silently replace the selected snapshot sources.

The option permits execution and runtime-linker verification opens of user
programs/libraries absent from the runtime manifest, so normal desktop package
installation remains possible. It does not relax the
independent kernel-module load check or checks on registered files. Enforced,
locked veriexec denies kernel/process-memory write overrides and live policy
control, including for root. Updates must use another boot environment rather
than overriding the running policy.
The kernel also refuses to start userland without a verified manifest handoff.
Without this option, upstream behavior is retained.

The EFI loader must enable `WITH_LOADER_VERIEXEC_PASS_MANIFEST` and verify a
signed runtime manifest before passing its digest to the kernel. Lua's module
loader puts module flags after the file name, which does not work for the
`pass_manifest` command's options. Use absolute paths in the runtime manifest
and this configuration, with no `runtime_flags`:

```
runtime_load="YES"
runtime_type="pass_manifest"
runtime_name="/boot/runtime.manifest"
```

Do not set `veriexec.manifest_hash` by hand as a replacement for signature
verification. The verified loader's handoff exports the digest it checked.

`tests/runtime-probe.c` checks exact kernel errors in a disposable guest. It
must not run against an operator's installed system: it attempts a module load,
opens a protected file for writing, and probes policy-control permissions.
The caller must first load and unload the trusted original module, then make
an unregistered copy. A duplicate-module error is not verification evidence.
The linker dispatcher returns `ENOEXEC` for the rejected module, so the serial
log must also contain the policy's explicit rejection diagnostic. Run
`python3 secureboot/tests/check-runtime-log.py valid <serial.log>`; its checks
require positive firmware, loader, policy and ordinary-program results, and
reject a panic or failed assertion. `missing-handoff` checks the corresponding
negative boot case and requires the specific kernel panic before userland.

Production enrollment, signed installation/update transactions, recovery and
ZFS/GELI qualification remain required before exposing this path to users.
