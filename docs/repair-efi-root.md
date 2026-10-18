# EFI loader cannot find loader.lua

The development installer previously registered its EFI entry with
`rootdev=zfs:POOL:`. FreeBSD interprets that as the pool's top-level dataset,
not the dataset named by its `bootfs` property. Daemonarchy installs `/boot`
in `POOL/ROOT/default`, so the loader reports `/boot/lua/loader.lua` missing
even though extraction succeeded. This affects both whole-disk and shared-disk
installs when firmware uses that EFI entry.

At the loader's `OK` prompt, run `show currdev` to get the pool name. Substitute
that name for `POOL` below (usually `zroot` for whole-disk installation, or
`daemonarchy-` followed by a unique suffix for shared-disk installation):

```text
set currdev=zfs:POOL/ROOT/default:
include /boot/lua/loader.lua
```

After booting, register a corrected EFI entry as root. Inspect `efibootmgr -v`
and verify the loader path before running the create command. For shared-disk
installs the path is `/boot/efi/EFI/Daemonarchy-POOL/loader.efi`; for whole-disk
installs it is `/boot/efi/EFI/FreeBSD/loader.efi`.

```sh
zpool get bootfs
efibootmgr -v
# Replace POOL and LOADER_PATH with the values verified above.
efibootmgr -a -c -L Daemonarchy -l LOADER_PATH -e 'rootdev=zfs:POOL/ROOT/default:'
```

The command creates a new entry; it preserves other operating systems' entries
and files. Verify its position with `efibootmgr -v` and reboot using the new
entry. Keep the installer USB available until the installed system boots.

The corrected installer reads the pool's `bootfs` property when creating its
EFI entry and records that complete dataset. This explicit entry selects the
dataset recorded at installation time; automatic tracking of subsequent
`bectl activate` changes and boot-once selection needs separate validation.

## Current signed-loader path

The explicit-dataset repair above is for the older loader. Current signed
1.1/1.1.1 payloads support `daemonarchy_rootpool=<decimal ZFS pool GUID>` and
follow the pool's active boot environment, including `bectl activate` and
rollback. The installer selects that path only with a validated matching signed
payload. Do not replace a current pool selector with a fixed dataset merely
to copy the historical workaround. See [Secure Boot authoring](https://github.com/jordanhubbard/daemonarchy/blob/main/secureboot/README.md)
and [the maintenance record](testing-1.1-upgrade.md).

## Regression checks

`bash tests/efi-root.sh` checks construction and validation of the EFI
environment. `tests/efi-boot-image.sh /new/output /snapshot/root [broken]`
runs as root on FreeBSD and creates a disposable ZFS/EFI disk with the
snapshot's real boot files. The optional `broken` argument writes the old
pool-only override; the default uses the installer's corrected environment.
It puts the environment in the ESP's `EFI/FreeBSD/loader.env` so the same
loader root-selection path can be exercised without changing host firmware.

Boot each image under UEFI QEMU with a serial console. The broken image must
report the missing Lua loader. The fixed image must initialize Lua and load
the kernel. These are boot-chain checks, not a complete installation or
physical-hardware qualification.

Checked on 2026-10-15 with the image build jail's October 5 FreeBSD EFI loader,
QEMU TCG, a Q35 machine and EDK II firmware:

- Old pool-only override: reproduced `cannot open /boot/lua/loader.lua: no
  such file or directory`, then stopped at `OK`.
- Corrected dataset override: read `/boot/defaults/loader.conf`, initialized
  Lua, loaded `/boot/kernel/kernel` and reached `OK` with autoboot disabled.
- Bash syntax, ShellCheck warnings (excluding sourced-variable warnings),
  EFI environment validation and `git diff --check`: passed.

The fixtures have no complete installed userland, so missing `/etc/hostid` and
`/boot/entropy` messages are expected. No full OS boot is claimed by this test.
