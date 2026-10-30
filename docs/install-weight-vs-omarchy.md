# Why Omarchy installs quickly and Daemonarchy slowly

Written 2026-10-30 as the investigation record for INSTALL-PERF-001 and PKG-002. Sources: Omarchy's latest
release, v4.0.6 (2026-10-19; a 4.5.0 release candidate exists), and `quattro` at
`5ea3d951` for the package lists (`install/omarchy-base.packages`,
`install/omarchy-other.packages`, `bin/omarchy-install-*`); the Omarchy 4.0.4 ISO;
a measured fresh-install manifest of an early 4.0 build
(`omarchy-iso/manifests/fresh-4.json`, version `4.0.0.alpha`, 940 packages);
Arch `core`/`extra` and the `omarchy` repository databases from Omarchy's
stable mirrors; Daemonarchy's 1.4.0 application feed
and `pkg.FreeBSD.org` `FreeBSD:16:amd64/latest`, measured with
`scripts/package-mirror-plan.py`, and the recovered live8 install record
(`verification/installer-live8-recovered-baseline-development.json`).
Omarchy's "about ten minutes" is its documented figure; it was not reproduced here.
The Omarchy package totals come from `scripts/omarchy-package-closure.py`, which resolves a
release's lists through the Arch and Omarchy databases; `nvim` is the one root those
databases do not carry, so the totals are a little low.

## Short answer

1. **We install a few more packages but about twice the bytes.** Omarchy v4.0.6
   resolves to about **918** packages in total: its 147 base entries plus the
   system packages (`base`, `linux-firmware`, `linux-omarchy`, `limine` and
   friends), 2.7 GiB of archives and 7.9 GiB installed. The method was checked
   against the one measured install: the 151 explicit packages of the `fresh-4`
   snapshot resolve to 948 against the 940 actually installed. Our 1.4.0 install
   has **1,189** packages (the fixed roots alone resolve to 1,002), 5.55 GiB of
   archives and 16.8 GiB installed: about 1.3 times the packages, **2 times the
   bytes**. The explicit lists are similar (147 for v4.0.6, 156 on `quattro`);
   our per-package weight is not.
2. **Omarchy installs most things up front, not on demand.** Its 156-entry base
   list includes `libreoffice-fresh`, `kdenlive`, `obs-studio`, `obsidian`,
   `chromium`, `clang`, `llvm`, `docker`, `dotnet-runtime`, `qemu-user-static-binfmt`
   and the Noto fonts including CJK. Only extras are on demand: editors, gaming,
   AI tools, services and browsers through `omarchy-install-*`, developer tools
   through `mise` stubs, web apps as launchers, and hardware-specific packages
   (`omarchy-other.packages`: NVIDIA, Broadcom, Apple, Framework, ...) that sit
   on the ISO's mirror and are installed only when the hardware matches.
3. **The gap is delivery.** Omarchy's ISO is **6.19 GB** because it carries the
   whole package mirror, and its README states the install reads packages
   straight off the medium and fetches nothing from the network. Ours is a
   3.5 GB image (1.59 GB as `.iso.xz`) with the Daemonarchy packages only; the
   other 3.78 GB of the 5.55 GB closure comes over the network during the
   install. On the live8 run that was 2,565 s of fetch against 141 s of package
   installation. On one Wi-Fi link on real hardware it is hours.

The count itself is not the problem; the bytes are. Removing the candidates
below would bring the installed size from about 16.8 GiB to about 11.5 GiB, nearer
Omarchy's 7.9 GiB, though not equal to it.

So moving packages on demand would shrink the ISO and the first install, but it
is not what makes Omarchy fast. Local delivery is. The two combine: carry a
small up-front core on the media, fetch the rest in parallel from a feed we
control (PKG-002), and make heavy optional applications opt-in.

## Where our weight is

Fixed-root closure: 1,002 packages, 5.13 GiB of archives, 15.52 GiB installed.
Marginal cost is what only that top-level dependency pulls in.

| Top-level dependency | Installed MiB | Archive MiB | Packages | Omarchy equivalent |
| --- | ---: | ---: | ---: | --- |
| `noto` (per-script families) | 2,242 | 1,492 | 58 | `noto-fonts`, `-cjk`, `-emoji` |
| `dotnet` (full SDK) | 1,175 | 727 | 4 | `dotnet-runtime` only |
| `libreoffice` (+ OpenJDK 25) | 929 | 355 | 46 | `libreoffice-fresh` |
| `libva-intel-media-driver` | 737 | 136 | 2 | installed only on Intel hardware |
| `kdenlive` | 667 | 144 | 115 | `kdenlive` |
| `obs-studio` (+ CEF) | 542 | 148 | 24 | `obs-studio` |
| `chromium` | 508 | 144 | 1 | `chromium` |
| `pinta` (+ Mono) | 274 | 83 | 9 | `pinta` |
| `wifi-firmware-kmod` | 244 | 67 | 50 | `linux-firmware` |

Also large and shared: `llvm19` 1,810 MiB (Omarchy has `llvm` and `clang` too),
`tesseract-data` 1,015 MiB installed and 423 MiB as an archive (every language;
Omarchy installs `tesseract-data-eng` only), `nerd-fonts-jetbrainsmono` 232 MiB
(Omarchy takes the `-basic` font), `deno` 310 MiB (a `yt-dlp` helper) and `gcc14`
359 MiB (pulled by NumPy and BLAS).

Candidates that Omarchy avoids or conditions: all-language OCR data, the full
.NET SDK, per-script CJK font families, the Intel media driver on non-Intel
machines, the full Nerd font, and the Intel/Mono/CEF chains behind optional
applications. Together these are about 5.3 GiB installed and 2.7 GiB of archive,
a third of the installed size and over half of the download. That is an upper
bound from catalogue sizes: each item still has to be checked for what breaks
if it is split or dropped.

## What to do (tracked in INSTALL-PERF-001 and PKG-002)

1. **Fix delivery first.** Fetch the closure in parallel from one signed feed we
   host (PKG-002), and carry a core set on the media so the first boot of a
   desktop reads from the medium. This is the largest and most certain gain.
2. **Trim the defaults.** Ship English OCR data, a runtime-only .NET, a smaller
   CJK font set and the Intel media driver only on Intel hardware, by splitting
   or replacing those packages in the ports fork. Measure the effect.
3. **Make heavy applications a choice.** Offer `kdenlive`, `obs-studio`,
   `libreoffice` and `pinta` as a selectable group with a stated size, default
   on or off by decision, installed after the base finishes or on demand from
   the menu as Omarchy's `omarchy-install-*` do.
4. **Measure with a trace.** The installer records a microsecond-resolution
   trace of every operation (see `docs/install-trace.md`), so each change is
   judged against the same per-operation baseline on the MSI, the MacBook and
   a VM.

Open question for the operator: the size of the media. Carrying the whole
closure would make the image about 9 GiB; the core-plus-feed design keeps it
near today's size.
