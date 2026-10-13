# 1.1 shallow checkout and driver development checks

Recorded on 2026-10-13. These are development checks, not full 1.1 release
acceptance. Implementation checkpoint: `b6673ef`.

## Live checkout packages

Both trees are depth-1 shallow Git checkouts. They contain working files and
`.git`, with one tracking branch; they do not include history back to the start
of either project. Users can deepen the history explicitly.

| Tree | Pinned revision | Tracking remote and branch | Download |
| --- | --- | --- | ---: |
| Ports | `6fb491f4c73a49b71b4843bbe2fd267953a59bc1` | `jordanhubbard/freebsd-ports`, `daemonarchy-1.1-iso` | 221.4 MiB |
| Source | `a52c50b4b7c2652954ef1bd34710a4b1fc8ef391` | `freebsd/freebsd-src`, `main` | 680.3 MiB |

The [catalogue](../overlay/usr/local/share/daemonarchy-installer/checkouts.json)
records exact package names, payload checksums, byte counts and space allowances.
The ports checkout uses a local `omarchy` branch tracking the published image
integration branch. The source checkout matches the October 5 image kernel,
not a moving CURRENT tip. The pre-release upstream refresh remains a separate
gate and requires new packages and a new catalogue.

| Check | Result |
| --- | --- |
| Shell/Python syntax, ShellCheck warnings, diff whitespace, local documentation links | Passed |
| Portable GPU selection and checkout option/capacity tests | Passed |
| Native FreeBSD pkg creation, installation and removal using a multi-part fixture | Passed |
| Fixture shallow depth, history deepening and local commits | Passed |
| Refusal to replace nonempty work; edits survive seed-package removal | Passed |
| Corrupt seed payload rejected before extraction | Passed |
| Real signed repository catalogue verification and installation of all three packages into an isolated root | Passed |
| Materialize both real working checkouts, clean Git status, expected revision and one commit | Passed |
| Source `__FreeBSD_version` matches the selected snapshot (`1600027`) | Passed |
| Existing BIOS disk-layout and shared-disk preservation tests | Passed, including both sector sizes and encrypted selection cases |
| Preview ISO build and archive payload inspection | Passed |
| Full installation with both options selected | Pending |

The real checkouts occupied approximately 1.1 GiB (ports) and 1.3 GiB (source)
on the test worker's compressed ZFS filesystem. Those figures are not universal
allocation requirements. The installer uses the larger measured peak-space
allowances, covering downloaded packages, installed seeds and extraction.

## NVIDIA and AMD payloads

The image includes `drm-66-kmod`, AMD/Intel firmware, `nvidia-driver`,
`nvidia-kmod` and `nvidia-drm-66-kmod`. NVIDIA 595.104.02 uses the explicit
6.6 DRM family so it can coexist with the image's AMD/Intel stack.

- `nvidia-driver-595.104.02` and
  `nvidia-drm-66-kmod-595.104.02.1600027` passed `poudriere bulk -t`, with
  two packages built and zero failed/skipped.
- `nvidia-kmod-595.104.02.1600027` was already built and passed the image
  admission audit, together with the DRM and firmware payloads.
- The native GPU package audit passed for 188 manifest entries. Actual kernel
  modules require the amd64 ABI and snapshot OS version. The architecture-neutral
  firmware metapackage is handled separately.
- Selection tests cover modern NVIDIA IDs, legacy exclusions, AMD Navi 14 and
  legacy Radeon, Intel/NVIDIA mixed graphics, modesetting, and missing payloads.
- Selected GPU packages are version-pinned and locked after installation.

The build worker's running kernel is `1600026`, older than jail `1600027`;
poudriere warns that this host/jail pairing is unsupported. Successful package
builds do not resolve that release qualification limitation. Physical NVIDIA/AMD
login, rendering, external displays and suspend/resume remain pending.

## Preview image

`daemonarchy-1.1.0-preview.2-amd64.iso` built successfully with all three NVIDIA
packages, AMD/Intel DRM and firmware, the checkout selection helper, runtime
command and pinned checkout catalogue present in the ISO. Its size is
2,079,694,848 bytes (1.937 GiB), below the 2 GiB release-asset budget.

SHA-256: `2501945fdae76af025179294db99159df14319e7d108e9134012ec6c2e702973`.

The desktop package remains 1.0.1, labelled as a drivers and shallow-checkouts
preview. The image build and archive inspection do not establish a complete
installation, a graphical desktop, or physical GPU acceptance.

## Full installation attempt

On 2026-10-13, the preview.2 bhyve test was started on a fresh 40 GiB
disposable disk with both `INSTALL_PORTS=true` and `INSTALL_SRC=true`.
The worker had 185 GiB free, approximately 3.1 GiB of free memory, and no
other active build or test VM. The guest requested 3 GiB of wired memory.
Immediately after bhyve launched, the worker became unreachable over SSH
and ICMP. The launch connection did not return an installation result.
This does not establish a guest failure or a host panic; console diagnosis
is required. Full installation and reboot remain **unverified**.

The test harness now checks selected trees after reboot as the installed
user: ownership, clean Git status, exact revisions, shallow depth, tracking
configuration, and source/kernel identity. Unselected trees must lack a
Git checkout. The bhyve harness also requires the installer success marker,
checks SSH login and firmware mode, and shuts down the guest after testing.
Shell syntax, ShellCheck, and whitespace checks passed for these harness
changes; the new post-boot assertions have not yet run in a guest.
