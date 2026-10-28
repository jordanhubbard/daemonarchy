# Lua-repaired live4 boot candidate, October 28

This unsigned development ISO repairs live4's loader splash and live-desktop
shortcut. The exact image passed default TUI and `T` live-mode boot checks.
The live case prepared its in-memory overlays and safely fell back to the TUI
because bhyve has no supported desktop GPU. It does not qualify desktop
rendering, installation, hardware or a release.

The [development observation](../verification/live4-lua4-candidate-20261028-development.json)
binds the image, inputs, preservation audit, native runtime checks and raw
evidence digests. The original [live4 record](testing-1.4-live4-20261027.md)
remains unchanged.

## Artifacts and inputs

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `daemonarchy-1.4.0-live4-lua4-amd64.iso` | 3,505,989,632 | `fd0ac2c85f428af6bcad260ea2a166816153b28c80ab244c92abf38085b9578e` |
| `daemonarchy-1.4.0-live4-lua4-amd64.iso.xz` | 1,572,734,780 | `14bcd8355299fa0e4c750ab0a4d467e0b94cd8b238f63a6acc51a7e4da1fbd29` |

Both size budgets pass. The compressed archive passes `xz -t` and decompresses
to the exact tested raw ISO digest. Each artifact has its own digest file.
The artifacts and private evidence remain on the existing workers; no large
image was copied to the controller.

The parent is live4 SHA-256
`56684b8d877a51b34a3027252abd2c55c63598112ea0416479e5a0654f0ea31e`.
Its native kernel, loader, world sets and retained 1.3.1 packages are preserved.
No kernel, world, ports or package compilation was invoked for this assembly.

The only regular-file byte changes are:

- `boot/lua/splash.lua` and `boot/lua/netdebug.lua` from source
  `95eb020f9bb769b9f0ecb53b60470104bf7324c6`,
  [source PR #40](https://github.com/jordanhubbard/daemonarchy-src/pull/40).
  They avoid Lua standard libraries the actual loader does not open.
- `boot/lua/menu.lua` from source
  `3d08a192a457f715664934fc84c461ae08c7615b`,
  [source PR #41](https://github.com/jordanhubbard/daemonarchy-src/pull/41).
  Boot trace uses `I`, leaving `T` available for the live desktop.

The world remains source `74f81f1949d5`, including the existing self-contained
boottrace-header fix ([source PR #39](https://github.com/jordanhubbard/daemonarchy-src/pull/39)).
The kernel remains `88f70f8d…`, the EFI loader `d2762e86…`; the complete
digests and the unchanged base/kernel/lib32/MANIFEST digests are in the record.
The installer still identifies itself as `1.3.1 (1.4 preview live4)`; no
version-string or source-catalogue restamp was performed.

## Filesystem and boot-format preservation

Assembly used the installed native Poudriere hybrid-ISO format recipe:
makefs cd9660/Rock Ridge with BIOS cdboot and the retained EFI image, etdump
to locate the EFI extent, then mkimg's protective MBR/GPT system area.
Both BIOS and UEFI boot entries are present. The boot tests below cover UEFI.

The final ISO was mounted read-only on native FreeBSD. Its 62,424 unique nodes
match the mounted parent in type, mode, numeric owner/group and symlink target.
Duplicate paths are rejected. All 56,815 regular-file digests match the parent
except the three declared Lua files. This verifies the embedded package
archives and installed live payload bytes without reinstalling packages.

The round trip must preserve ISO-specific structure:

- A mounted-filesystem PAX copy preserves the logical Rock Ridge paths;
  a direct archive-reader extraction misplaced deep paths.
- The private extraction directory's permissions must not become the ISO root.
  The final root is `0755`, and the guest verifies live-user traversal.
- Existing extent sharing is restored only for groups that share the same LBA
  and size in the parent, with matching file bytes and metadata. This restores
  13,277 aliases and 3,139,415,184 shared data bytes, including rescue tools.
  It does not deduplicate unrelated files by content.
- The empty formatter-owned relocation directory is omitted from the inputs
  and regenerated once; copying it back as an input produced a duplicate entry.

Rejected attempts and displaced staging copies are retained privately. The
preservation audit, raw size budget and unique-path checks rejected those
attempts before qualification. The native tools' observed digests are recorded;
their complete runtime input closure is not claimed.

## Exact-image boot checks

Both native bhyve cases used fresh 16 GiB targets, UEFI, two vCPUs and 4 GiB.
The actual framebuffer menu was captured and reviewed before selection.
Kernel/runtime state was collected through the serial login.

| Case | Observed result |
| --- | --- |
| Default TUI, Enter | Kernel source identity `74f81f1949d5`; TUI mode; root `0755`; live account can traverse and execute the retained runtime files. |
| Live desktop, T | `daemonarchy_live=YES`; live ready marker; expected tmpfs overlays; root/traversal checks pass. The unsupported virtual GPU triggers safe TUI fallback. |

Each guest powered off normally. Each entire target had SHA-256
`07d217ebccc55480b7afa191674ec5da87f2d14efbc04dbc7e40efe345f16776`
before and after. No installation ran.

The earlier serial-only loader-menu harness timed out during firmware splash
output although the framebuffer showed the menu. The final cases select
through the actual video console and retain that failed harness attempt.
PTY software flow control is disabled and local carrier handling is explicit.

On Sparky, QEMU/OVMF TCG booted the exact same ISO with no serial device.
224 retained VGA frames show the animated wordmark/mascot and the normal menu.
The composed 20 Lua files pass the missing-standard-library guard; the splash
controls pass with table/math absent. The fixed source commits also have green
controller and native-loader CI.

## Qualification boundary

The retained installation `base.txz` is unchanged. The current installer expands
it and copies branding afterwards; it does not copy these three fixed boot Lua
modules into the installed system. **The installed-system Lua fix and an actual
installation/installed boot remain open.** The inherited optional source-checkout
catalogue/feed mismatch from the parent record was not repaired or retested.

Real GPU desktop rendering, audio, kernel-bound external GPU/Wi-Fi modules,
physical MacBook/MSI runs and Secure Boot remain unqualified. This work did not
touch the prepared MSI hardware-trace stick; that separate image and its
delivery evidence remain preserved.

No native action was admitted to the retained release graph, no cache hit or
lifecycle receipt was manufactured, and nothing was signed, tagged, merged or
published. These are development boot observations, not release acceptance.
