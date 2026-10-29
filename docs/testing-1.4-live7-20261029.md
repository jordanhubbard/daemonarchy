# 1.4 live7 acceptance candidate (unsigned) (2026-10-29)

This is a development record of an unsigned candidate for the MacBookPro16,1
and MSI acceptance runs. It does not qualify a release. Nothing was signed or
published. The evidence is kept on `daemon.local` under
`/usr/daemonarchy/live7-20261028`.

live7 replaces [live5](testing-1.4-live5-20261028.md) and live6 as the
candidate. live6 was built from daemonarchy-src `bac4c23cacae`, which lacks
src#45 (isavga on UEFI) and src#46 (atrtc on UEFI). The MSI
[dev10 run](testing-msi-dev10-20261028.md) showed that both are needed for the
stock configuration to reach init.

## Inputs

- **Product:** `origin/main` at `95a4760c6cdf`, exported unchanged. It includes
  #115 (the Apple T2 internal link stays off DHCP) and #117 (remote worker).
- **Kernel, loader and world:** daemonarchy-src `daemonarchy` head
  `da95f20bcceb` (live6's `bac4c23cacae` plus src#45 and src#46), fresh
  `--depth 1` clone, clean objdir, `-j8` on `daemon.local` (8 cores).
  - World 3 h 15 min (11,676 s), kernel 14 min, sets 10 min. All passed.
  - Kernel identity: `FreeBSD 16.0-CURRENT #0 daemonarchy-da95f20bcceb`.
  - `__FreeBSD_version` 1600029, as live6.
- **Sets:** `base.txz` `cc2317c2…`, `kernel.txz` `a90e4f51…`,
  `lib32.txz` `a8567552…` (MANIFEST verified).
- **Jail:** `16live7da95f`. `/usr/src` matches the built tree and the jail
  kernel is byte-identical to the built kernel.
- **Packages:** live6's candidate repository, copied. The copy is
  byte-identical to it (`repo-copy-identical`, 1,470 files). The src#45 and
  src#46 changes are kernel-only, so no package was rebuilt. The
  `security/t2-touchid` port merged after live6 is not in this image.
- **Checkout catalogue:** the 1.3.1 ports entry unchanged and a new src
  checkout receipt for `da95f20bcceb`.

## Artifacts

| File | SHA-256 |
|---|---|
| `daemonarchy-1.4.0-live7-amd64.iso` (3,507,167,232 bytes; 250,929,152 below the limit) | `4170ef606aa36c109251d993f1889b8cbcbb136702893196bfb91570af41c1c9` |
| `daemonarchy-1.4.0-live7-amd64.iso.xz` (1,573,779,244 bytes) | `4d0caf4795a070ef1f06939019e163d247d28428ed1fc22b9eb68277e8e826dd` |

## Results

- **Native test suite** (`daemon.local`, FreeBSD 16.0-CURRENT, against the
  product tree): all 20 tests pass, including `installer-progress` and
  `installed-boot-network`, which failed on live6.
  - A first run hung in `remote-debug-background` because it was started with
    `nohup … &` from a non-interactive shell, which leaves SIGINT ignored for
    the test's Ctrl-C step. It was rerun detached with `daemon(8)` and passed.
    This was a launch problem, not a product failure.
- **Acceptance stick:** the raw ISO was written to a 7.5 GB USB stick and read
  back: the first 3,507,167,232 bytes match the ISO's SHA-256 above.

## Not done

- No fresh install, installed boot, live-desktop VM case or network VM case
  has been run on the exact live7 bytes (ledger A11, A13, A14 stay open).
- No physical run on the MacBookPro16,1 or the MSI Raider 18 HX has been
  recorded yet.
- Nothing is signed, and the feed and boot bundle are not published.
