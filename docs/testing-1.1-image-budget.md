# 1.1 live image size qualification

Historical 1.1 development/candidate evidence. Revisions, checksums and results
below apply to the named artifact and date; they do not qualify the new
[1.1.1 source/package set](testing-1.1.1.md). Follow that record for current
preparation and publication status.

Recorded on 2026-10-15. This qualifies the live-image trimming change, not
the complete 1.1.0 release or its outstanding feature requirements.

| Image | Raw ISO bytes |
| --- | ---: |
| preview.10 | 2,371,284,992 |
| preview.11 | 1,872,025,600 |
| Saved | 499,259,392 |
| Headroom below the 2 GiB release-asset limit | 275,458,048 |

The new image is `daemonarchy-1.1.0-preview.11-amd64.iso`. Its SHA-256 is:

```text
7a52f5c2e463fcd82ff224c4c4e5350ee4e5c98377344ffcba2d3f63b9f50653
```

`scripts/live-image-excludes` removes the live root's compiler/linker/debugger
toolchain, compiler resources, C/C++ headers and static libraries. It also
removes the 32-bit loader and `ldd32`; the 32-bit libraries were already
excluded. Those development tools remain available in the installed system
because its `base.txz` is unchanged. GPU and Wi-Fi payloads remain on the ISO.
Source and ports seed packages were already downloaded only on selection;
the ISO retains the same 2,144-byte checkout catalogue and both options.

## Checks

- Actual tar exclusion behavior and sparse-file budget boundary tests passed
  on macOS and FreeBSD. The gate accepts 2 GiB minus one byte, and rejects
  both exactly 2 GiB and the previous oversized image's byte count.
- Shell syntax, ShellCheck at warning severity, and whitespace checks passed.
- Native poudriere hybrid-ISO build passed with the same snapshot and packages.
- The final image passed the new size gate and its copied checksum verified.
- Archive inspection found no excluded development paths and confirmed that
  the package-file set matches preview.10 exactly.
- Embedded `base.txz` and `kernel.txz` hashes match the snapshot's `MANIFEST`;
  the checkout catalogue matches the source byte for byte.
- `tests/live-image-runtime.sh` passed on FreeBSD: required live commands and
  payloads exist, Bash/Gum/jq/pkg-static execute, and all scanned retained
  dynamic ELF programs/libraries resolve their dependencies within the ISO.
  Temporary devfs/ISO mounts and the allocated md device were cleaned up.
- The copied ISO booted under QEMU UEFI to the welcome screen and installer
  options menu. The smoke VM had no target disk and was stopped afterward.

Build/audit logs, serial output and console captures are retained locally in
`~/Library/Logs/Daemonarchy/2026-10-15-preview11/`. The ISO and checksum are in
`~/Downloads/` and on the build worker in `/usr/local/poudriere/data/images/`.

No full installation of preview.11, BIOS boot, graphical desktop or physical
hardware check is claimed here. The build host's kernel remains older than
the snapshot jail (1600026 versus 1600027); the prior host qualification
limitation remains. This development image has not been published as a release.

## Preview.12

The next development image includes `omarchy-4.0.4_15`,
`daemonarchy-1.0.1_2,1`, the enterprise Wi-Fi helper and its Python runtime,
and installer revision `7399015575401c9d64cd2391db1c02517266b8f8`.
Its ports checkpoint is `0b4e3743af34` on `daemonarchy-1.1-iso`.

The ISO is **1,922,754,560 bytes**, leaving **224,729,088 bytes** below the
2 GiB limit. SHA-256:

```text
991091b06dbac0a1f254be12627cee7ae338aba72ffc6935bb41c512a2301bc8
```

The native live-runtime audit passed, including enterprise helper imports and
all scanned retained dynamic ELF dependencies. Copies on the operator machine
and QEMU worker match this checksum. Python pruning removes its development
archive, regression suite and duplicate optimized caches from the live root;
the desktop Python package and installed FreeBSD development system remain
complete. The snapshot and build-host qualification limitation are unchanged.
