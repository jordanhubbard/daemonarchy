# 1.5.0 hardware trace image with the network hand-over: QEMU record (2026-10-31)

Development record for [DEBUG-004](roadmap/active-work.md). It qualifies nothing
on hardware. Nothing was published and no signing key was used.

## Inputs

- Product: the branch of this change on `origin/main` 1e1b56d4
  (`build-hwtrace-image.sh`, `tools/hwtrace/`, `tools/boottrace/stick.py`).
- Kernel, loader, Lua, `/rescue`, `sshd` and libraries, modules: the 1.4.1/1.5.0
  amd64 candidate ISO built from `68bb08b8`
  (`daemonarchy-1.4.1-amd64.iso`, SHA-256 `63be3d00...d87a09`). The kernel is
  `FreeBSD 16.0-CURRENT #3 303b3646270f` and the loader is `boot/loader_lua.efi`
  from that ISO; `brand-daemonarchy.lua` and `local.lua` are left out of the
  Lua directory. Nothing in `secureboot/`, the kernel, loader or any package is
  changed by this work.
- Build host: the mudflap VM, `nice -n 15`, under
  `/usr/daemonarchy/trace-mvp-20261031`; each build takes about 10 s.
- Test host: madmax, QEMU 10.2.1/KVM with OVMF, `~/trace-mvp/`, a SATA stick,
  an e1000 NIC on user networking with `2222` forwarded.

## Images

| Image | Bytes | SHA-256 |
| --- | ---: | --- |
| `daemonarchy-hwtrace-1.5.0-amd64.img` (published form, no keys) | 410,027,520 | `2d2c2ace...afa0` |
| `daemonarchy-hwtrace-1.5.0-amd64.img.xz` | 20,073,584 | `745c5e26...fccf2` |
| `daemonarchy-hwtrace-1.5.0-msi-amd64.img` (private: operator keys, `-H`, MSI queue) | 410,027,520 | `1f905cf7...97e891` |

The root is 96 MiB UFS (about 69 MB used), the ESP 40 MiB, DATRACE 256 MiB.

## Scenarios (`tools/boottrace/qemu-trace-mvp-test.py`, test key, `-S` image)

| Scenario | Result |
| --- | --- |
| `handover`: normal experiment reaches init, DHCP (10.0.2.15), sshd on 2222; the baked key logs in as root, a second key is refused, the host key equals the one built with `-H`, `pciconf`/`netstat` run, `hwtrace-continue` ends the hold, the loop stops, the stick has `ADDRESS.TXT`, `DUMPS/0001/network.txt` and the usual dumps | PASS |
| `hang`: experiment 1 hangs at `attimer0` (silent, machine reset by the harness after 90 s), the trace is filed INCOMPLETE, experiment 2 boots, hands over, and the loop stops | PASS |
| `bounded`: `hwtrace.hold=20`, nobody connects: the boot reboots by itself about 38 s after sshd came up, sshd is gone, the loop stops | PASS |
| `nokey`: an image with no keys reaches init, never opens port 2222, reboots and the loop stops as before | PASS |
| Exact private MSI image (no serial): sshd answers, `ADDRESS.TXT` carries the fingerprint of the `-H` host key (`SHA256:eMVA4401...`) | PASS (login not tried: the operator's private key was not used) |
| Published image + `stick.py keys` (test key) + a queue: sshd answers, the key logs in, host name `daemonarchy-hwtrace`, `ADDRESS.TXT` | PASS |

## Findings fixed on the way

- The rescue `sed` is BSD basic-regex: `\|` alternation matched nothing, so a
  stick with keys was treated as keyless. `net.sh` uses a `case` loop.
- `rescue/dhclient-script` is a real script, not a multi-call name; sshd needs
  `sshd-session` and `sshd-auth`; `dhclient` wants `/var/run/dhclient` and the
  `_dhcp` account.
- GENERIC already has em, igb, igc, ix, re and rge built in; loading their
  modules printed "already loaded from kernel". The module list is now USB
  Ethernet plus bge and msk.
- Userland console output (the rc banner) did not reach the QEMU serial line
  or the video screen; the hand-over is therefore recorded on the stick
  (`ADDRESS.TXT`, `network.txt`, `rc.log`), and the screen message is best
  effort.

## Not verified

Physical hardware of any kind (the MSI's RTL8125 under `rge`, a USB Ethernet
dongle, the MacBook); a real DHCP server and router; Secure Boot (the image
needs it off); that the banner shows on a physical console; sshd from a client
other than OpenSSH 10 on Linux; the `-S`-less image's loader on the MSI.
Wi-Fi is not supported.
