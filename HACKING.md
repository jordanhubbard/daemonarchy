# Hacking on Daemonarchy

This is the guide for people who want to change Daemonarchy, build it themselves, or test and release what they built. [README.md](README.md) says what Daemonarchy is and what is the same as FreeBSD; this page assumes you have read the "Is it still FreeBSD?" section there and want your hands on the source.

If you already hack on FreeBSD, the good news is that you mostly keep your habits. You still edit a source tree and run `make`; you still edit a port and build it. What Daemonarchy adds is a layer of packaging and release machinery around those trees, so the question this page answers first is: *where does my change go, and what do I run to see it on a machine?* The first half of this file is a narrative for that. The second half, starting at [Reference](#reference), is the full runbook with every tool, test and pitfall the project has met; nothing from the old version of this file was dropped.

Latest published release: **1.5.0** ([`release/current.json`](release/current.json)),
daemonarchy-src `303b3646270ffa4bf7cec65c5c1d28bd8000cbce` (OSVERSION `1600029`),
daemonarchy-ports `e84b4c4cde0df8ee645ee46e7ad1e99ef8ffa181` on `main`. Keep base,
kernel, jail, drivers, optional source checkout and signed manifests on that
selection. The [1.5.0 release notes](docs/release-1.5.0.md) record its qualification
and limits; [1.4.1](docs/release-1.4.1.md) and the earlier 1.1.1 selection stay in
their records ([1.1.1](docs/testing-1.1.1.md)).
Older image examples below must use their own retained inputs; a package update
is not a base/ABI migration.

**In this half:** [the big picture](#the-big-picture) · [FreeBSD muscle memory, the Daemonarchy way](#freebsd-muscle-memory-the-daemonarchy-way) · [what you need](#what-you-need) · [four walkthroughs](#walkthrough-1-change-the-installer-and-test-it) · [running the tests](#running-the-tests) · [how a release happens](#how-a-release-happens) · [Literate AI](#literate-ai-what-it-is-and-whether-you-need-it) · [what is rough](#what-is-rough-today)

## The big picture

A Daemonarchy image is five things stacked up, each with its own repository (the [full table](#the-repositories-that-make-up-daemonarchy) is in the reference):

1. **FreeBSD itself**, from [daemonarchy-src](https://github.com/jordanhubbard/daemonarchy-src): an ordinary FreeBSD source tree, a fork that tracks upstream FreeBSD `main` and keeps Daemonarchy's own changes on an integration branch (`daemonarchy`). It produces the base system, the kernel and the 32-bit libraries as tarball sets.
2. **The ports**, from [daemonarchy-ports](https://github.com/jordanhubbard/daemonarchy-ports): the FreeBSD ports tree plus the Omarchy ports. Poudriere builds them into packages, and the ones Daemonarchy publishes itself are signed and uploaded as GitHub release assets (the "feeds").
3. **The desktop layers**, [omarchy-freebsd](https://github.com/jordanhubbard/omarchy-freebsd) and [daemonarchy-desktop](https://github.com/jordanhubbard/daemonarchy-desktop). They are not built separately: the ports `x11-wm/omarchy` and `x11-wm/daemonarchy` fetch them at pinned commits, so they reach a machine as packages.
4. **The installer and the image**, this repository: the installer in `overlay/`, `build-iso.sh`, `pkg-repo.sh`, the test harnesses, the release scripts and the documentation.
5. **Evidence and release records**, also this repository: `verification/`, `release/current.json`, and the gates that refuse a release that does not prove its inputs.

A change travels the same way whichever layer it starts in:

```
daemonarchy-src --(build.py or make)--> base.txz kernel.txz lib32.txz
                                               |
                                     poudriere jail (16amd64)
daemonarchy-ports --(poudriere bulk)--> packages --(pkg-repo.sh)--> signed feeds
daemonarchy-desktop, omarchy-freebsd --(pinned in ports)--^
this repo: overlay/ + build-iso.sh --(poudriere image)--> ISO
        --(test-qemu.sh / test-bhyve.sh)--> QA --(operator signs)--> publish
```

Two things to carry in your head:

- **Most of your day is spent in one of three loops.** Installer or overlay change: edit, build an ISO, install it in a VM. Port change: edit, `poudriere testport`, merge, pin. Base change: edit `/usr/src`, build, and only then think about how it reaches an image. The walkthroughs below do one of each, then the ISO.
- **The release pins everything by full commit.** A release is a set of exact commits (installer, source, ports) plus exact feed tags and asset checksums. Nothing is built from a moving branch tip.

## FreeBSD muscle memory, the Daemonarchy way

This is the table to read if you are a FreeBSD developer. The left column is what you would type today on a plain FreeBSD machine. The right column is what a Daemonarchy developer runs, checked against the scripts in this repository and in daemonarchy-src. "Same" means the command works identically because the tree is FreeBSD's.

| On plain FreeBSD you... | On Daemonarchy you... | Notes |
|---|---|---|
| `cd /usr/src`, edit, `make buildworld buildkernel` | **Same**, in any daemonarchy-src checkout on FreeBSD (`/usr/src` is the conventional place). For release inputs, run the pinned, unprivileged controller instead: `python3.12 tools/daemonarchy/build.py plan` then `run`, from the daemonarchy-src checkout. | The tree is stock FreeBSD underneath ([its README](https://github.com/jordanhubbard/daemonarchy-src/blob/main/README.md) still points at `build(7)`). The controller adds a frozen plan, isolated object and staging directories, per-phase logs and byte-verified results. It refuses to run as root. |
| `make installworld installkernel DESTDIR=/`, reboot | **Same commands** on a build host or a throwaway VM. On an installed Daemonarchy machine this is *not* a qualified path today (the project has no base or kernel upgrade it has tested; see [the upgrade model](#the-upgrade-model-today)). | If you try it, make a boot environment first (`sudo daemonarchy-be create`, or `bectl create`). With Secure Boot enforcement on, the firmware boots the signed kernel and not yours. GPU and Wi-Fi modules are packages built for one exact kernel and have to be rebuilt after a kernel change. |
| `cd /usr/src/release && make release` to get an ISO | There is no `make release` step for the Daemonarchy ISO. `build-iso.sh` assembles it with `poudriere image` from a jail made from your `base.txz`, plus the packages. The `sets` phase of `build.py` produces the tarballs the jail is made from (it uses the release Makefile's `packagesystem`). | `ARCH=aarch64 ./build-iso.sh` on a native arm64 host makes the arm64 image. |
| `cd /usr/ports/<category>/<port> && make all install` | **Same**, in a daemonarchy-ports checkout (on a Daemonarchy machine, `sudo daemonarchy-checkouts ports "$USER"` puts one at `/usr/ports`). To try a port on a running Daemonarchy desktop, `sudo make reinstall clean` in its directory. | Daemonarchy adds nothing around a plain `make` in a port. It adds a clean-room test (`poudriere testport`) and a rule about which ports ship from Daemonarchy's feed ([walkthrough 2](#walkthrough-2-build-one-port)). |
| `poudriere bulk -j <jail> -p <tree> -f list` | **Same**, with `-b latest` so poudriere fetches the official packages it can reuse: `poudriere bulk -j 16amd64 -p omarchyiso -b latest -t -f omarchyiso-ports.list`. The release pipeline wraps this as `scripts/build-release-packages.sh`. | The origin lists are `ISO_ORIGINS`, `OMARCHY_ORIGINS` and `LIVE_ORIGINS` in `origins.sh`. |
| `pkg install`, `pkg upgrade`, `bectl` | **Same.** `daemonarchy-be` is a wrapper around `bectl` for the menu. | The menu's **Update** saves a boot environment first; `sudo pkg upgrade` alone does not. |
| `bsdinstall` | `./test-qemu.sh <iso>` or `sudo ./test-bhyve.sh <iso>` drives the Daemonarchy installer unattended in a VM. | Answers come from a `daemonarchy-install.conf` on a drive labelled `CIDATA`; see the [installer reference](docs/installer-reference.md#unattended-installs). |
| `freebsd-update` or `git pull && make installworld` as the upgrade path | **Not available.** A new snapshot, kernel or boot bundle arrives as a new image. | [The upgrade model](#the-upgrade-model-today) is the plain statement. 1.5.1 plans network upgrades. |
| A faster build because someone wrote a better driver | Not delivered. The plan to make builds much faster with Literate AI (BUILD-001) is deferred to 1.5.1 with zero evidence ticked, and 1.5.0 makes no speed claim. | Everything above is the hand pipeline the project actually used for 1.5.0. |

## What you need

### The machine you build on

What the repository documents, by job. Nothing here is a hidden requirement; where a number comes from a particular run it says so.

| To do this | You need | Evidence |
|---|---|---|
| Edit docs, the installer overlay and the Python and shell tooling; run the portable tests | Any Linux, macOS or FreeBSD machine with `git`, `python3` and `bash` (CI uses Python 3.13; builders use `python3.12`). `lua5.4` for one loader test. | The CI jobs in `.github/workflows/` run the portable tests on `ubuntu-latest`. |
| Install-test an ISO | Anywhere QEMU runs (Linux, macOS, FreeBSD), no root: `qemu-system-x86_64` (or `qemu-system-aarch64`), UEFI firmware (OVMF; AArch64 edk2 for arm64), an OpenSSH client, and `mkfs.fat`/`mtools` or `xorriso` for the CIDATA drive. On an x86 host with acceleration it is fast; on a non-x86 host the guest is emulated and an install takes two to three hours. Or FreeBSD with VT-x/AMD-V, root and `edk2-bhyve`, for `test-bhyve.sh`. | Headers of `test-qemu.sh` and `test-bhyve.sh`. The harness creates a blank 40 GB guest disk and gives the guest 4 GiB (`MEM`, default `4G` for QEMU, `3G` wired for bhyve). |
| Build world, kernel and installer sets | A **native FreeBSD 16.0-CURRENT** machine of the target architecture (amd64 is the documented target), with `git`, Python 3.12 and `/usr/local/sbin/pkg`, an unprivileged build account, **at least 80 GiB free** on the output volume, and at least **2 GiB of RAM per job (8 GiB minimum)**. Keep objects and staging outside the source tree and outside `/usr/obj`. | `tools/daemonarchy/README.md` in daemonarchy-src. A clean `buildworld` took 7,931 s and the whole producer about 9,360 s on an 8-vCPU, 16 GiB guest at `-j4` ([build baselines](docs/roadmap/release-1.5.1.md#baselines-recorded-first-with-where-measured)). |
| Build the packages and the ISO | A **native FreeBSD 16.0-CURRENT** machine of the target architecture, **as root**, with `poudriere`, `git`, the pinned ports tree and a jail made from the image's own sets. Linux and macOS cannot do this step: `poudriere image`, jails and `makefs` are FreeBSD's. | `build-iso.sh` header. The maintainers' amd64 builder is a FreeBSD 16-CURRENT VM with 16 vCPU, 48 GiB RAM and a 500 GB sparse disk; the arm64 builder is a separate native arm64 VM ([mastering notes](docs/mastering-1.5.0.md)). The 1.1.1 dependency rebuild used 20 CPUs, 80 GiB and 400 GiB with two package builders. |
| Master a release | The amd64 builder, a QA host that runs QEMU, and at least 30 GB free in the work directory. | `scripts/master-release.sh` preflight. |
| Sign anything | A separate, protected host holding the keys. You do not need one to develop; **agents and builders never hold key material**. | [One signing session per release](#one-signing-session-per-release). |

Expect the first package build to be long. When the pinned ports tree is ahead of what pkg.FreeBSD.org has built, poudriere rebuilds what does not match, which can include compilers and browsers; the pitfalls list records a chromium and LibreOffice build taking most of a day. Later builds reuse the persistent caches described in [Persistent authoring caches](#persistent-authoring-caches).

### What to install on the machine

Package names below were checked against daemonarchy-ports. On a FreeBSD 16.0-CURRENT builder:

```sh
pkg install git gh jq bash python312 poudriere xorriso
```

- `poudriere-devel` can replace `poudriere` (the maintainers' VM runs poudriere-devel 3.4.99). `gh` is only needed where you create GitHub releases or upload feeds; `jq` is used by `build-iso.sh` and the release steps; `bash` is the interpreter of `master-release.sh` and `build-release-packages.sh`; `xorriso` is what the builder uses for the hybrid ISO.
- For `test-bhyve.sh` add `edk2-bhyve` (the package `sysutils/edk2` builds for bhyve). For `test-qemu.sh` on FreeBSD add `qemu` and `mtools`.
- On Debian or Ubuntu, `test-qemu.sh` wants `qemu-system-x86` (and `qemu-system-arm`), `ovmf` (and `qemu-efi-aarch64` for arm64), `mtools`, `dosfstools` and `xorriso`, plus `git`, `python3`, `bash` and `lua5.4` to run the portable tests. The harness looks for OVMF at `/usr/share/ovmf/OVMF.fd` and takes `OVMF=` to override it.
- `xz`, `openssl`, `makefs`, `mkimg` and `bsdtar` are in FreeBSD's base system.
- Shell scripts are checked with `shellcheck` in CI (`devel/hs-ShellCheck` on FreeBSD).
- Literate AI is optional; see [its section](#literate-ai-what-it-is-and-whether-you-need-it).

### Which repositories to check out, and where

Start with the installer repository; it is the one you always need.

```sh
git clone https://github.com/jordanhubbard/daemonarchy.git ~/src/daemonarchy
```

| Repository | Check it out when | Where, and which branch |
|---|---|---|
| [daemonarchy](https://github.com/jordanhubbard/daemonarchy) | Always | Anywhere. Branch from `main`; the release machinery masters from a clean checkout of one full commit. |
| [daemonarchy-src](https://github.com/jordanhubbard/daemonarchy-src) | You change the kernel or base system, or build the sets | `/usr/src` is the conventional path and the optional checkout the installer offers uses it; `~/daemonarchy-src` also works for the controller. `main` tracks upstream FreeBSD; Daemonarchy's changes and the optional `/usr/src` checkout use the `daemonarchy` branch. Check out an exact commit (`git checkout --detach <40-hex>`) for any build you will keep, and keep the tree clean while it builds. |
| [daemonarchy-ports](https://github.com/jordanhubbard/daemonarchy-ports) | You change or add a port, or build packages | `main` is the integration branch (the 1.5.0 pin is `e84b4c4c` on it). Register it with poudriere as a null tree (`poudriere ports -c -p omarchyiso -m null -M <path>`); on a Daemonarchy machine it can also be `/usr/ports`. A shallow clone is enough for poudriere. |
| [daemonarchy-desktop](https://github.com/jordanhubbard/daemonarchy-desktop) and [omarchy-freebsd](https://github.com/jordanhubbard/omarchy-freebsd) | You change the look, the System > FreeBSD tools or the FreeBSD adaptation of Omarchy | Anywhere (`~/src`). The ports fetch them pinned, so test your checkout by laying it over the port's extracted sources ([The FreeBSD layer and the desktop layer](#the-freebsd-layer-and-the-desktop-layer)) and then bump the pin in the port. |

A Daemonarchy machine can fetch most of this for you. **System > FreeBSD > Hack on Daemonarchy** (`daemonarchy-dev-setup`) clones omarchy, omarchy-freebsd, daemonarchy-desktop, this repository and a ports tree into `~/src`. One thing to know: in the desktop repository's `main` as read for this page, that script clones the older `jordanhubbard/freebsd-ports` fork on its `omarchy` branch, not daemonarchy-ports, and it does not clone daemonarchy-src. For 1.5.0-era work, clone daemonarchy-ports and daemonarchy-src yourself.

The maintainers keep a parallel workspace under `/usr/daemonarchy` (independent `src`, `ports` and `control` checkouts with `obj`, `stage`, `packages`, `cache` and `evidence` beside them, on their own ZFS dataset) so experiments never touch the machine's running system; see the [workspace plan](docs/roadmap/native-workspace.md). You do not need that layout to start.

## Walkthrough 1: change the installer and test it

The installer is shell, in `overlay/usr/local/libexec/daemonarchy-installer/` (`configurator` asks, `install` installs, `dashboard` draws). It is the quickest thing to change because it does not need a new package set.

1. **Edit, and run the portable tests that cover it.** For example, after touching `install` or `package-repository`, `bash -n overlay/usr/local/libexec/daemonarchy-installer/install` and `sh -n overlay/usr/local/libexec/daemonarchy-installer/package-repository` (CI does both), and the suites under [Running the tests](#running-the-tests).
2. **See it without an install.** `dashboard` draws from a log file, so you can try the install screen by feeding it one; the recipe is in [The installer](#the-installer) in the reference.
3. **Build an ISO** on the FreeBSD builder, as root, from your checkout. The package repository and sets are reused, so an installer-only change takes minutes, not hours:

   ```sh
   cd ~/src/daemonarchy
   JAIL=16amd64 PTREE=omarchyiso ./build-iso.sh
   ```

   What you will see: `==> ISO staging: /var/tmp/...` (each run gets a new private staging directory and keeps it), `==> Collecting the Omarchy package repository` with a package count, checks that the sets match the jail and the checkout catalogue, then `poudriere image`. The image and its `.sha256` land in `/usr/local/poudriere/data/images`, named `daemonarchy-<VERSION>-<arch>.iso`. Set `NAME` and `PREVIEW_LABEL` for a development image so its welcome screen says what it is.
4. **Install it in a VM, unattended.** Copy the ISO to any machine with QEMU and run:

   ```sh
   WORK=$PWD/qemu-run ./test-qemu.sh daemonarchy-1.5.1-amd64.iso
   ```

   The harness boots the ISO with a blank 40 GB disk and a `CIDATA` drive that carries the answers, waits for the installer to power the guest off, boots the installed disk, logs in over SSH and checks what a VM without a screen can show (accounts and groups, SDDM's user and session, services, the Daemonarchy feed). It prints each check and a tally. The serial console is in `$WORK/install.log` and `$WORK/boot.log`, which is where to look first when an install stalls. On FreeBSD with bhyve use `sudo ./test-bhyve.sh <iso>` instead (`NET=nat` by default; `./test-bhyve.sh --cleanup` removes the test network afterwards).
5. **Gotchas.** Give the guest real memory and do not overcommit the host (a swapped-out guest can trip the kernel's deadlock detector mid-install). Under emulation use a CPU model without AVX (the harness does) because ZFS's AVX2 code faults under `-cpu max`. For arm64, `ARCH=aarch64 ./test-qemu.sh <iso>`, and use `-device e1000e` for the known virtio-net issue in [docs/aarch64.md](docs/aarch64.md). The [pitfalls](#pitfalls-met-so-far) list has the rest.

## Walkthrough 2: build one port

This is the "`cd /usr/ports/category/port && make all install`" loop. There are three levels, from quick to shippable.

**Try it on a running Daemonarchy machine.** Get a ports tree (the installer offers one, or `sudo daemonarchy-checkouts ports "$USER"` later; it is a shallow clone of daemonarchy-ports `main`, about 4 GB with the space allowance), then work in it as you would on FreeBSD:

```sh
cd /usr/ports/x11-wm/omarchy        # any category/port
make                                # fetch, extract, patch, build
sudo make reinstall clean           # install over the installed package, then clean
```

`seed-user --force` re-copies Omarchy's defaults into your home if the port changes them (it never overwrites a file you have changed). The installed system keeps its compiler, headers and libraries, so building a port on it works.

**Test it in a clean room.** Do not run `make stage-qa` as root on a host you care about, because it installs the port's dependencies onto the host. Use poudriere on the builder:

```sh
poudriere testport -j 16amd64 -p omarchyiso -o x11-wm/omarchy
```

That builds the port in a clean jail and checks stage-qa, the plist, install and deinstall.

**Ship it.** A change to a port reaches users only through one of two doors, and which one depends on `origins.sh`:

- If the origin is in `OMARCHY_ORIGINS` (the Omarchy ports and the few packages Daemonarchy carries because the official packages lack a fix), it is built by Daemonarchy and published in the signed feed, so `pkg upgrade` delivers it. Bump `PORTREVISION` whenever the package contents change (poudriere rebuilds on version changes, not file changes), run `make makesum` if you changed a pin, and open a pull request against daemonarchy-ports `main`. Releasing the rebuilt package is a feed publication, described in [How a release happens](#how-a-release-happens).
- Any other port comes from pkg.FreeBSD.org's own builders, so the way to ship a fix to it is upstream FreeBSD. Add the origin to `origins.sh` only if Daemonarchy must carry its own build.
- Kernel-bound ports (`*-kmod`, firmware, NVIDIA) are on the ISO, not in the online feed, and rebuilding one moves the Secure Boot module inventory and the signed boot bundle. That is a release-owner decision.

Gotcha: a port that changes `x11-wm/omarchy` or `x11-wm/daemonarchy` is pinning a commit of omarchy-freebsd or daemonarchy-desktop. A desktop fix reaches users only after the pin bump and a new package in the feed.

## Walkthrough 3: build FreeBSD itself

There are two ways, and they answer different questions.

**"I changed a driver and want to see it compile and boot."** This is plain FreeBSD. In your daemonarchy-src checkout on a FreeBSD 16.0-CURRENT machine, run `make buildworld buildkernel` (and the rest of `build(7)`) as you always do; the tree is FreeBSD's. Use a VM or a spare machine, and do it in a boot environment if it is a Daemonarchy install, for the reasons in the [muscle memory table](#freebsd-muscle-memory-the-daemonarchy-way).

**"I need world, kernel and sets I can trust and hand to the image build."** Use the controller that lives in the source fork, because it freezes the inputs and records what it built:

```sh
git clone https://github.com/jordanhubbard/daemonarchy-src.git ~/daemonarchy-src
cd ~/daemonarchy-src
git checkout --detach <full-40-hex-commit>
mkdir -p ~/daemonarchy-builds

python3.12 tools/daemonarchy/build.py plan --revision <full-40-hex-commit> \
    --output ~/daemonarchy-builds/baseline-<short> --jobs 8
python3.12 tools/daemonarchy/build.py run  --revision <full-40-hex-commit> \
    --output ~/daemonarchy-builds/baseline-<short> --jobs 8
python3.12 tools/daemonarchy/build.py status --output ~/daemonarchy-builds/baseline-<short>
python3.12 tools/daemonarchy/build.py verify --output ~/daemonarchy-builds/baseline-<short>
```

Use the same arguments for `plan`, `run` and a resumed run. The phases are `buildworld`, `buildkernel`, `packages` (pkgbase packages), `release-obj` and `sets` (`base.txz`, `kernel.txz`, `lib32.txz`, `src.txz` and `MANIFEST`). Each phase has a six-hour default deadline. `--through buildkernel` stops after compilation; `--resume` continues the same plan; `--profile diagnostic` builds a kernel with startup tracing compiled in (use a fresh output directory). `plan` writes `plan.json`, binding the commit, tree, configuration and commands; `run` writes logs and `result.json`; `verify` checks the recorded bytes. Expect hours. It never installs, signs, uploads or reboots anything, and it refuses to run as root.

What you will not get from this: a ready ISO, or proof that the result boots. External ports modules (GPU and Wi-Fi drivers) are excluded and have to be rebuilt against this exact source and kernel. Before a source-built set replaces the snapshot sets a release uses, the owned build still has to pass a VM boot and install, a matching jail and modules, update and rollback, signatures and physical hardware; that checklist is in daemonarchy-src's `tools/daemonarchy/README.md` ("Promotion to Daemonarchy"). The documented release path is still the verified snapshot sets of the pinned source revision: `scripts/cache-release-sets.sh` fetches and checksums them into `SET_CACHE_DIR` (default `/var/cache/daemonarchy-iso`), and the jail is made from them.

To make that jail (as root, once per snapshot; the poudriere details and the `@clean` snapshot trap are in [Setting up a build host](#setting-up-a-build-host)):

```sh
sh scripts/cache-release-sets.sh
poudriere jail -c -j 16amd64 -a amd64 -v 16.0-CURRENT -m tar=/var/cache/daemonarchy-iso/base.txz
tar -xpf /var/cache/daemonarchy-iso/kernel.txz -C /usr/local/poudriere/jails/16amd64
tar -xpf /var/cache/daemonarchy-iso/lib32.txz  -C /usr/local/poudriere/jails/16amd64
```

## Walkthrough 4: build an ISO

With a jail, a pinned ports tree registered with poudriere, and a bulk-built package set, the image is one command. The whole sequence from nothing is long, so here it is as a map; each step is explained in the reference ([Setting up a build host](#setting-up-a-build-host)):

1. Make the jail from the sets (above) and register the ports tree (`poudriere ports -c -p omarchyiso -m null -M <path>`).
2. Put the package build settings in `/usr/local/etc/poudriere.d/omarchyiso-poudriere.conf` (build the GPU and Wi-Fi modules locally rather than fetching them: `PACKAGE_FETCH_BLACKLIST`, `PACKAGE_FETCH_URL`, `DISTFILES_CACHE`).
3. Bulk-build the origins from `origins.sh`: `poudriere bulk -j 16amd64 -p omarchyiso -b latest -t -f omarchyiso-ports.list`.
4. `./build-iso.sh`, as root.

`build-iso.sh` is configured through its environment. The ones you will meet:

| Variable | Meaning |
|---|---|
| `ARCH` | `amd64` (default) or `aarch64`; the host must be native to it. It chooses the jail, set cache, feeds and boot file. |
| `JAIL`, `PTREE` | The poudriere jail and ports tree (defaults `16amd64` and `omarchyiso`). |
| `SET_CACHE_DIR`, `SNAPSHOT_URL` | Where the verified `base`, `kernel` and `lib32` sets are cached, and where missing ones come from. |
| `POUDRIERE_ETC`, `POUDRIERE_DATA` | An isolated poudriere configuration and its data directory. |
| `OUTDIR`, `NAME`, `PREVIEW_LABEL` | Where the image goes, what it is called (default from the `VERSION` file), and a label the welcome screen shows for a development image. |
| `ISO_STAGE_PARENT` | Parent of the private staging directory (default `/var/tmp`). |
| `PACKAGE_REPOSITORY_TAG`, `PACKAGE_REPOSITORY_PUBLIC_KEY` | Which signed application feed the image pins, and its public key. A fork passes its own. |
| `PACKAGE_MIRROR_URLS`, `REQUIRE_PACKAGE_MIRROR=yes` | The signed closure-feed shards a release image prefers to pkg.FreeBSD.org, and the refusal to build without them. |
| `CHECKOUT_CATALOG` | The signed checkout feed catalogue (defaults to the one in the overlay). |
| `SECUREBOOT_BUNDLE`, `SECUREBOOT_SIGNATURE`, `SECUREBOOT_CERTIFICATE` | The signed boot bundle, signature and public certificate (public artifacts only; see [Secure Boot development](#secure-boot-development)). |
| `LIVE_EXTRA_OVERLAY` | A private directory laid over the live root (for private firmware previews). |

Every `build-iso.sh` run creates a new staging directory and prints it; failed and finished ones stay for inspection. The ISO is written next to a `.sha256`, and the release image is also published xz-compressed (the build checks that the `.xz` decompresses to exactly the built image and that it fits the 2 GiB asset limit). `bash tests/live-image-budget.sh` checks the size boundaries; on FreeBSD, `sudo sh tests/live-image-runtime.sh <iso>` audits the live root's commands and shared libraries read-only.

## Running the tests

There is no single `make test`. The suites are standalone Python and shell programs under `tests/`, and CI runs them one by one (`.github/workflows/`). Most need nothing but the standard library, run on any machine, and finish in seconds. Start with the three that guard the documentation and the release record, which are the ones every pull request must keep green:

```sh
python3 tests/docs-release-sync.py -v     # docs agree with release/current.json
python3 tests/docs-lifecycle.py -v        # links, anchors and reachability from SKILL.md
python3 tests/version-sync.py -v          # one release version everywhere
```

What you will see is unittest's ordinary output, ending like this:

```
Ran 13 tests in 0.072s

OK
```

When `docs-release-sync` fails it lists `path:line: problem` for each stale claim, such as a document that calls an older release "current" or an image name or checksum from a previous release. Fix the document; do not weaken the guard.

Other portable suites, as CI runs them (a few more take `-I`, which isolates Python from the working directory):

```sh
python3 tests/package-mirror-plan.py -v ; python3 tests/release-check-1.4.py -v
python3 -I tests/plugins-and-games.py -v ; python3 -I tests/extension-bundles.py -v
python3 tests/install-trace.py -v ; python3 tests/parallel-fetch.py -v
bash tests/master-release.sh ; bash tests/build-release-packages.sh
bash tests/live-backend.sh ; bash tests/live-desktop.sh ; lua5.4 tests/loader-live-menu.lua
```

The complete list is the set of `tests/*.py` and `tests/*.sh` that `.github/workflows/release-14-controls.yml` and `native-graph.yml` invoke. A handful of those (the ones the CI "controls" job runs after installing the framework wheel) import `literate_ai`, so they need Literate AI installed.

Other suites need a FreeBSD host, root, or both, and mount memory disks or build pools: for example `sudo bash tests/disk-layout.sh`, `sudo bash tests/boot-environment-mounts.sh`, `sudo bash tests/shared-disk.sh`, `sudo bash tests/pkg-repo-dependencies.sh` and `sudo bash tests/checkout-packages.sh`. Each is introduced where the reference section it checks is described ([Testing](#testing), [Releasing](#releasing)). They exercise real mounts, so run them on a disposable FreeBSD VM, never on a machine you care about. VM install tests (`test-qemu.sh`, `test-bhyve.sh`) are the integration level above these; none of this proves a graphical desktop on physical hardware, which has its own records under `docs/`.

## How a release happens

The release is a sequence of resumable steps, driven by `scripts/master-release.sh` and recorded step by step in a state file so a rerun resumes. The reference [Releasing](#releasing) section is the full procedure; this is the shape.

1. **Pin** one daemonarchy-ports commit and one daemonarchy-src commit, and set the version once with `python3 scripts/version.py set X.Y.Z`.
2. **List what changed** against the last release's feed with `scripts/diff-release-packages.sh`, which only evaluates `make -V PKGNAME` and builds nothing.
3. **Build**: `master-release.sh packages` (poudriere, seeded from the previous set so retained packages are not rebuilt), `secureboot` (regenerate the module inventory; re-signing is the operator's), `feed` (collect and sign the application feed on the builder, which holds the key), `resolve`, `catalogue`, `iso`, `verify`, `hwtrace` and `qa`. `master-release.sh --dry-run --config master.env all` prints every command without running anything; `all` never writes sticks and never publishes.

For planned 1.6 split media, follow [the transport and record procedure](docs/split-media.md).
Authoring requires explicit manifest pins and separate raw-image/download fields.
The mastering verifier, hwtrace extractor, QA transfer and stick writer accept an
explicit pinned split selection. Packed ARM inspection checks the reconstructed
root independently. `inspect` is static-only; from planned 1.6, `verify` requires
native Python/SQLite execution through read-only mounts and returns unrun without
success on other controllers. Complete exact final-image native/physical acceptance before
publishing split assets.

4. **Draft the release pull request** with `scripts/prepare-release.py` (placeholders) and `scripts/fill-release.py` (from the verified artifacts), and check staged assets with `scripts/verify-release-assets.py`. The documentation guard is expected to fail until the placeholders are filled; that is why the pull request stays a draft.
5. **Sign and publish are the release owner's steps**, in one signing session: the feeds, the boot bundle and the GitHub release. Nobody and nothing else holds those keys.
6. **Bring the documents into step**: `scripts/release-current.py update` rewrites `release/current.json` from the published release, then `tests/docs-release-sync.py` shows every document that still carries the old release.

Where you are in all this as a contributor: open a pull request against `main`; leave the pinning, signing and publishing to the release engineers listed in the README. See [Contributing](#contributing).

## Literate AI: what it is and whether you need it

**Short answer: you do not need it to build, test, change or release Daemonarchy.** Every command in the walkthroughs above is a plain shell, Python or `make` command. Literate AI (`litai`) is a separate project, [jordanhubbard/literate-ai](https://github.com/jordanhubbard/literate-ai), and nothing here is built by it.

**What it is.** A release-engineering and software-lifecycle tool built around specifications: you declare the product's contracts (what the installer, the desktop, the package engine and so on are responsible for), pin them with locks, and record evidence (receipts) of what was built and tested. Daemonarchy adopted it "in place": the existing scripts remain the implementation and release authority, and Literate AI sits beside them as a checking layer. Its footprint in this repository is `literate.project.json`, `literate.release.json`, the eight Component contracts under `components/`, the work queue in [docs/roadmap/active-work.md](docs/roadmap/active-work.md), `SKILL.md` and `AGENTS.md` (which tell coding agents how to behave here), and the architecture map in [design-traceability.md](docs/architecture/design-traceability.md).

**Where it is installed.** Not on the ISO, not in the package feeds, and not in any port. A port and package ("LITAI-PKG-001") is a queue item for after 1.5, unscheduled. `litai` is a Python package (Python 3.11 or later) that you install yourself, side by side with whatever else you have, in its own virtual environment: on a laptop or workstation for the authority checks, and on a FreeBSD build worker for native build work. CI installs it by building a wheel from a pinned framework revision (the "controls" job in `release-14-controls.yml`); you can do the same:

```sh
git clone https://github.com/jordanhubbard/literate-ai.git
git -C literate-ai checkout 0a267a6646f20e3a635a1f870042b6b034f026a1   # the revision CI pins
python3 -m venv ~/litai-venv
~/litai-venv/bin/pip wheel --no-deps --wheel-dir ~/litai-wheels ./literate-ai
~/litai-venv/bin/pip install ~/litai-wheels/literate_ai-1.4.0-*.whl
~/litai-venv/bin/litai --version
```

The project's lifecycle binding names an exact framework distribution. The framework's newest published release when this page was written was v1.3.1, which is not what the project pins, so build from the pinned revision, which is a development build of the framework's next version. The checks reported below were run with a development build of the same line; the procedure for moving to another framework build ("rebind") is in [native-adoption-steps.md](docs/native-adoption-steps.md). Do not replace a stable `litai` you rely on elsewhere.

**What it does in 1.5.x, command by command.**

| Role | Command | What happens |
|---|---|---|
| Authority gate | `litai project validate .` | Checks that the project definition, the eight Components, the authority graph and the documentation graph are coherent: no cycles, documentation reachable, links and anchors that resolve. Passes on `main`. |
| Component locks | `litai lock --check` (also part of `verify`) | Confirms the eight committed Component locks match their contracts. Passes on `main`. |
| Everything declared | `litai verify` | Runs every declared gate and writes nothing, builds nothing and calls no model. See the outcome below. |
| Documentation review | `litai project documentation-review` | Prints the value a human records as the `authority-reviewed` marker in `docs/architecture/design-traceability.md` after reviewing the documentation. Editing documentation makes that marker stale until a person re-reviews. |
| Work records | `litai work record` | Allocates a stable ID for a new item in the work queue; update requirements, acceptance evidence and the changelog together. |
| Release check | `litai release check` | Runs `scripts/release-check-1.4.py`, the 1.4.x gate (see below). |
| Retained-project builds | `litai build --retained-project MANIFEST --retained-project-profile PROFILE` (add `--retained-project-plan` for a read-only plan) | Plans, and only with the operator's explicit authorization executes, a build from an exact, frozen input manifest on a registered FreeBSD worker. Prototype stage; see below. |

The 1.4.x release gate (`literate.release.json` names it) refuses to pass unless the release record names exactly this version and checkout, `release/current.json` has no placeholder, `litai verify` passes for the `authority` and `locks` gates, the standard-library documentation, version and lifecycle suites pass, and the staged assets match the record. It needs `DAEMONARCHY_RELEASE_RECORD` and `DAEMONARCHY_RELEASE_ASSETS` (and `DAEMONARCHY_CLOSURE_ASSETS` when the record has closure feeds). It says in its own header that it does not claim the native test receipt.

**What `litai verify` says today, honestly.** On `main` before these documentation changes it reported: `authority` pass, `locks` pass (8 current), `source-intelligence` skipped, `html-observability` skipped and `receipt` **fail** (`project.test_receipt_missing: configured project test receipt has not been committed`), with exit status 1. The receipt is `verification/current.json`, which a retained native build would earn; it does not exist, so that gate is red, and **it is red on purpose**. Do not write a receipt by hand or paste in an old log to turn it green. A change to promote a retained run into a receipt is open in the framework as [literate-ai #297](https://github.com/jordanhubbard/literate-ai/pull/297) ("Add project test-receipt promote-retained"); until it lands and a native run is promoted, expect the receipt gate to fail and report it that way. After a documentation change, expect `authority` to report the documentation marker stale until a human re-attests it. That is also by design.

**The advantages, as actually delivered.** One command that answers "is the declared design coherent, are the docs reachable and the contracts locked?" and fails closed. A release gate that refuses placeholders, another version or commit, authority or lock failures and asset mismatches. Stable work IDs and a queue that records evidence beside requirements. Instructions for coding agents that make them keep to the project's authority rules. **What the advantages are not:** faster builds (the plan to cache and run native builds incrementally, BUILD-001, is deferred to 1.5.1 with no evidence ticked), a driver for `build-iso.sh` (the 1.5.0 release was assembled with the hand pipeline in this file and `scripts/master-release.sh`), or a green receipt.

**Where it is headed.** The retained-project builds are the interesting part. A draft profile is in `tools/retained-draft/` (its [PROVENANCE.md](tools/retained-draft/PROVENANCE.md) lists what is captured and what is unknown), and daemonarchy-src has a selected-unit prototype. They are prototypes: execution needs the operator's authorization, and `litai` runs trusted project code unconfined, so nobody should run them casually. [native-adoption-steps.md](docs/native-adoption-steps.md) lists the steps and what is still open.

**What you can do without it.** All of: clone the repositories; build the sets, the ports and the ISO; run `test-qemu.sh` and `test-bhyve.sh`; run every `tests/*` suite except the few that import `literate_ai`; publish a package feed with `pkg-repo.sh`; master a release with `master-release.sh`; use the documentation guards (`tests/docs-release-sync.py`, `tests/docs-lifecycle.py`). What needs it: `litai project validate`, `litai verify`, `litai lock`, `litai release`, `litai work` and retained native builds, and the release gate because it calls `litai verify`.

## What is rough today

Honest list, so you do not discover it by accident.

- **The project test receipt is red** (above): there is no `verification/current.json`, so `litai verify` fails on `main` and will until a retained native run is promoted.
- **No tested path to upgrade the base on an installed machine.** `make installworld` on a Daemonarchy install is an experiment; the project's own base and kernel upgrade (NETUP-001) is planned for 1.5.1.
- **Source-built sets are not yet a qualified release input.** `build.py` produces them, byte-verified, but the release path documented in this file is the pinned snapshot sets.
- **Scripts default to the maintainers' paths.** `master-release.sh` and `build-release-packages.sh` default `WORK` to `/usr/daemonarchy/...`, the jail to `16r2303b36` and the ports tree to `daports141`; `pkg-repo.sh` defaults `BUILD_HOST` to `freebsd.local`. Set the environment (or a `master.env`) for your own machines. A fork also has to replace the hard-coded `jordanhubbard/daemonarchy` URLs; see [Forking Daemonarchy](#forking-daemonarchy), which is the honest list because there is no fork guide yet (FORK-001, planned for 1.5.1).
- **`build.py` and `build-iso.sh` cannot share one invocation:** the first refuses to run as root, the second must run as root.
- **No single test command**, and some suites need a FreeBSD VM and root.
- **Documentation authority marker** is a human attestation and goes stale on any documentation edit; that is expected.
- **The arm64 image is community-validation only,** with the known virtio-net issue; the NVIDIA RTX Spark laptop is deferred.

# Reference

Everything below is the runbook as it stood before the narrative above was written, kept whole: the repositories and how they are pinned, the upgrade model, forking, where files live, build host setup in detail, changing each layer, testing, remote debugging, the hardware trace image, releasing, pitfalls, Secure Boot development and the live checkout packages. Links elsewhere in the repository point at these section names, so they have not been renamed.

## Literate AI project authority

The plain-language version of this section, with install steps and what `litai verify` reports today, is [Literate AI: what it is and whether you need it](#literate-ai-what-it-is-and-whether-you-need-it). What follows is the project's authority rules as they stood.

Read [PROJECT.md](PROJECT.md), [the active queue](docs/roadmap/active-work.md) and
[the architecture](docs/architecture/design-traceability.md) before changing
cross-component behavior. Literate AI (the framework release pinned in
[the release controls workflow](.github/workflows/release-14-controls.yml)) validates the in-place
contracts; original source and the native commands below retain implementation
and release authority. Automatic quarantine conversion was not applied.

Run `litai project validate .` for authority checks and `litai verify` for the
complete declared gate report. The latter must continue to report a missing
current native receipt until ADOPT-002 qualifies native execution and release custody.
No generated source, native qualification or publication permission follows from
a metadata check. Keep signing keys and private worker evidence outside Git.
For 1.4.x, `scripts/release-check-1.4.py` is the gate `litai release check` runs: it needs
`DAEMONARCHY_RELEASE_RECORD` and `DAEMONARCHY_RELEASE_ASSETS` (and
`DAEMONARCHY_CLOSURE_ASSETS` when the record has closure feeds) and refuses placeholders,
another version or commit, authority or lock failures and asset mismatches; it does not
claim native execution or the LitAI receipt. The earlier
native release gate, `scripts/release-check-1.3.1.py`, required the
current LitAI authority and locks plus a separately retained, hashed native
build record. Its release record must bind `native_evidence_sha256`; set
`DAEMONARCHY_NATIVE_RECORD` and `DAEMONARCHY_NATIVE_EVIDENCE_ROOT` to the
reviewed private record and logs. This does not make the missing LitAI project
test receipt pass or qualify the planned 1.4 LitAI executor.

Use `litai work record` for new stable work IDs. Update the owning requirements,
acceptance evidence and changelog together. A prospective implementation change
must explicitly refresh its retained source baseline; metadata-only adoption
checks must preserve original implementation bytes. Native commands and platform
requirements remain in this runbook. PERF-001 permits replacing the build
executor after equivalent correctness and measured performance are demonstrated;
generated wrapper commands alone do not establish that qualification.

## The repositories that make up Daemonarchy

The five owned product repositories below supply the selected implementation;
Literate AI is a separate authority and build toolchain input. Pin exact commits
for each release. File-level detail is in [Where things live](#where-things-live).

| Repository | What it is | Installed or used by |
|---|---|---|
| [daemonarchy](https://github.com/jordanhubbard/daemonarchy) (this one) | The installer, its overlay, the live image, the package feed and image scripts, the tests, the documentation and the release engineering (release records, gates, mastering). | It is the product; the ISO, the signed Secure Boot bundle and the feeds are published from it. |
| [daemonarchy-desktop](https://github.com/jordanhubbard/daemonarchy-desktop) | The Daemonarchy look and FreeBSD tools over Omarchy: artwork (`wallpaper.svg`, `wordmark.svg`, `mark.svg`, `about.txt`, `screensaver.txt`), the SDDM theme, the System > FreeBSD menu (`omarchy-menu.jsonc`) and the `daemonarchy-*` commands (boot environments, home snapshots, jails, bhyve VMs, DTrace views, dev setup). | Installed by the port `x11-wm/daemonarchy`. |
| [daemonarchy-ports](https://github.com/jordanhubbard/daemonarchy-ports) | The forked FreeBSD ports tree: packaging recipes (Makefiles, plists, patches) only. Default branch `main`. | Poudriere builds our feeds from it; the installer's `origins.sh` names the ports we publish ourselves. |
| [daemonarchy-src](https://github.com/jordanhubbard/daemonarchy-src) | The forked FreeBSD source tree: the base system and kernel. Default branch `main`. | The image's world, kernel, pkgbase and installer sets, and the kernel-bound modules, are built from it. |
| [omarchy-freebsd](https://github.com/jordanhubbard/omarchy-freebsd) | The FreeBSD compatibility layer for Omarchy (`freebsdize.in`, `compat/`, `freebsd-bin/`, `seed-user`, ...). | Fetched by the port `x11-wm/omarchy` as a second distfile, pinned at `3e8359b47c28` in the port. |
| [literate-ai](https://github.com/jordanhubbard/literate-ai) | The independently versioned framework and `litai` CLI for contracts, locks and release controls. | Used in selected controller and development environments; packaging it for installed systems remains [LITAI-PKG-001](docs/roadmap/active-work.md#litai-pkg-001-ship-literate-ai-as-a-port-and-package-so-users-run-srcports-operations-with-litai). |

The `x11-wm/omarchy` port also fetches pinned
[basecamp/omarchy](https://github.com/basecamp/omarchy) source. The owned
`jordanhubbard/omarchy` fork is not selected by that port. FreeBSD's upstream
source and ports are synchronization inputs for the owned forks.

Every repository our packages are built from, by the ports' `GH_ACCOUNT`/`GH_PROJECT`/`GH_TUPLE`
lines on daemonarchy-ports `main`:

- `x11-wm/daemonarchy` fetches `jordanhubbard/daemonarchy-desktop` at a pinned commit (`GH_TAGNAME`,
  `ec2a00824ec9` at 1.4.1; `DISTVERSION` 1.5.0 since 1.5.0 (ports #46), with a `v` prefix, so the version in the port is not a tag
  of the desktop repository, whose last tag is `v1.1.1`).
- `x11-wm/omarchy` fetches `basecamp/omarchy` (upstream Omarchy, not the `jordanhubbard/omarchy` fork)
  plus `jordanhubbard/omarchy-freebsd`.
- `ports-mgmt/daemonarchy-pkg` (the graphical package manager) fetches `jordanhubbard/daemonarchy`
  (this repository) at a pinned commit.
- No other port in the tree fetches from a `jordanhubbard` repository. Everything else comes from the
  upstream projects the FreeBSD ports name. A search of the Makefiles only sees the `GH_*` form; a port
  that fetches by another mechanism would be missed (*unverified*).

Why the desktop is not folded into the ports fork: the ports tree holds packaging recipes, and a
Makefile cannot sensibly hold artwork, a menu and shell tools that change independently of the
FreeBSD ports tree, which is also refreshed from upstream on its own schedule. The port pins the
desktop's commit, so a desktop fix reaches users only after a pin bump in daemonarchy-ports and a new
package in the feed. The desktop repository is separately applicable and carries its own history (the
1.5.0 plan records this check).

Other repositories under the same GitHub account (Aviation, ElixirSSI,
project-tracker, bookscan, freebsd-sentiment, LeRTX and the Literate AI labs)
are not product source inputs.
`jordanhubbard/freebsd-ports` is the older ports fork, used for releases through 1.1.1 and for upstream
submissions; releases since use daemonarchy-ports.

### Where a change goes

| Change | Repository |
|---|---|
| Artwork, the login theme, the System > FreeBSD menu, the `daemonarchy-*` tools | daemonarchy-desktop, then a pin bump in `x11-wm/daemonarchy` (daemonarchy-ports) |
| Installer logic, overlay, live image, ISO and feed scripts, tests, documentation | daemonarchy |
| Package recipes, port patches, new or updated ports | daemonarchy-ports |
| Kernel, base system, drivers in the base tree | daemonarchy-src |
| Omarchy's FreeBSD adaptation, compat shims | omarchy-freebsd, then a pin bump in `x11-wm/omarchy` |
| Framework CLI, native lifecycle or executor capability | literate-ai; requalify its selected distribution and the affected product contracts and gates |
| Launchers and menu entries now in the installer overlay (Cudalab, Wine, Steam) | daemonarchy today; [DESKTOP-001](docs/roadmap/active-work.md#desktop-001-ship-the-desktop-launchers-and-menu-entries-in-the-daemonarchy-desktop-package) moves them to daemonarchy-desktop |

### How the pieces are pinned, versioned and released together

- A release record (`verification/release-VERSION.json`, schema `daemonarchy/release-inputs@1`) names the
  exact installer commit, daemonarchy-src commit, OSVERSION, daemonarchy-ports commit and the feed tags, and
  every published asset's size and SHA-256. `release/current.json` names the latest published release.
- The product tag is `daemonarchy-X.Y.Z` on this repository. The signed package feeds are published
  as GitHub release tags on this repository, named like `packages-16-amd64-X.Y.Z` and
  `checkouts-16-amd64-X.Y.Z` (a suffix such as `-r2` when a published tag could not be reused; published
  tags are immutable).
- daemonarchy-src and daemonarchy-ports are selected by full commit, not by branch tip, and kept fixed through
  qualification. The ports fetch their own GitHub sources by pinned commit as above.
- daemonarchy-desktop has no tag convention that matches the port today (last tag `v1.1.1`, port pins a
  commit). The recommendation, to be settled in the repository's own project file, is to follow the
  product version and tag at release.
- Literate AI has its own version and exact framework distribution identity.
  A passing authority check is not native build, package or release evidence.
- [Releasing](#releasing) has the procedure; `scripts/release-check-1.4.py` is the gate `litai release check` runs.

### Contributing

There is no CONTRIBUTING file in this repository (*checked*). Work on a short-lived
topic branch and submit a pull request to the owning integration branch: product
`main`, source/ports `daemonarchy`. CI must pass and a maintainer merges. Do not
commit to a release branch, and do not push signing keys, private worker evidence or generated images.
Upstream FreeBSD or Omarchy fixes are submitted upstream independently of Daemonarchy releases.

## The upgrade model today

Stated plainly, as of 1.5.0 on main; the evidence and the gaps are in [the 1.5.1 plan](docs/roadmap/release-1.5.1.md).

- **`pkg upgrade` (and the desktop's Update) upgrades applications**, from the signed feeds published as GitHub
  release assets. The desktop's Update saves a boot environment first (*unverified here*: implemented in
  omarchy-freebsd); `sudo pkg upgrade` alone does not.
- **It does not upgrade the FreeBSD base, the kernel, the kernel-module packages on a verified install, the
  loader or EFI files, or trust.** No base, kernel or pkgbase feed is published. A feed built for a newer
  `OSVERSION` is refused on an older base (`scripts/adopt-candidate-packages.sh`). Modules are locked to the
  signed inventory. A new package-signing key or Secure Boot certificate arrives with a new image.
- **Same-snapshot boot maintenance** (`daemonarchy-secureboot stage` and `activate`, a signed bundle, a new boot
  environment) exists as a development tool with 1.1-era QEMU evidence. It has not been qualified on the 1.4 line
  and is not a supported update command.
- **No upgrade between releases was accepted for 1.4.0 or 1.4.1.** An ISO is still how you move to a release
  that changes the snapshot, the kernel or the boot bundle, and the supported way to get 1.5.0's rebuilt Wi-Fi
  module and boot bundle. 1.5.0 is not promised to be the last ISO release.
- 1.5.1 plans network upgrade of base, kernel, modules and boot files with boot-environment rollback (NETUP-001),
  trust rotation (NETUP-002), upgrade QA on exact artifacts (NETUP-003) and forkability (FORK-001).

## Forking Daemonarchy

A fork is possible but not yet easy; FORK-001 plans one configuration and a guide. What a fork must do today,
from the repository (checked with `git grep jordanhubbard`):

1. **Fork the five owned product repositories** ([which are which](#the-repositories-that-make-up-daemonarchy)) and keep
   daemonarchy-ports pinned to your source and desktop commits.
2. **Generate your own package-signing key** with `pkg-repo.sh keygen` on your build host, commit its public half
   as `overlay/usr/local/share/daemonarchy-installer/daemonarchy.pub`, and keep the private key off Git.
   Generate your own Secure Boot certificate and sign your own bundles (`secureboot/README.md`); `maintenance.py`
   only accepts source commits listed in its `SOURCE_OSVERSIONS`, so add yours.
3. **Replace every hard-coded `jordanhubbard/daemonarchy` URL**: the installer's feed URL and its validation
   patterns (`install`, `package-repository`), `build-iso.sh`, `test-qemu.sh`, `checkouts.json`
   (feed and the source and ports remotes), `extensions.json`, the release scripts' repository defaults
   (`release-current.py`, `verify-release-assets.py`, `package-feed-*.py`, `pkg-repo.sh` `GH_REPO`) and the two
   ports that fetch from `jordanhubbard` repositories (`x11-wm/daemonarchy`, `ports-mgmt/daemonarchy-pkg`).
   Pass your key and tag to `build-iso.sh` through `PACKAGE_REPOSITORY_PUBLIC_KEY` and `PACKAGE_REPOSITORY_TAG`.
4. **Have a builder.** FreeBSD 16.0-CURRENT with poudriere, a snapshot jail and the ports tree for each
   architecture you publish, as in [Setting up a build host](#setting-up-a-build-host), and a place to sign.
5. **Publish** the feeds to your own GitHub releases with `pkg-repo.sh upload` and the feed scripts, then
   build and test the ISO.
6. **Keep the notices**: licenses, the Omarchy and FreeBSD credits and the trademark statement in the README.

What breaks if you change only the repository name: the installer refuses its own feed URL, the image points
at our feeds and checkouts, and `verify-release-assets.py` checks our repository. Untested: an end-to-end fork
by someone else; this list is from reading the code.

## Where things live

Daemonarchy spans the installer, desktop, compatibility, source and ports repositories:

- **This one** builds the installer image:
  - `overlay/usr/local/libexec/daemonarchy-installer/`: the installer. `launch` runs from root's login on the live system; `configurator` asks the questions (it vendors Omarchy's own setup form); `install` partitions, installs, and configures; `dashboard` draws the install screen from the install log.
  - `overlay/usr/local/libexec/daemonarchy-installer/install-integrity`: checks installed package files and dependencies before the installer records success. A nonzero result retains a failed installation and its rescue evidence.
  - `overlay/usr/local/libexec/daemonarchy-installer/rebuild-caches`: rebuilds the caches the packages' pkg triggers maintain (GSettings schemas, GIO modules, icon and MIME caches), which `pkg -r` cannot (see Pitfalls).
  - `overlay/usr/local/libexec/daemonarchy-installer/fix-ownership`: restores the owners, groups and modes packages record, which `pkg -r` loses when installing into the target (see Pitfalls).
  - `overlay/usr/local/share/daemonarchy-installer/`: the installer's logo, the loader brand, the keymap table, and the package repository's public key (`daemonarchy.pub`).
  - `origins.sh`: the ports whose packages Daemonarchy publishes itself, rather than taking them from pkg.FreeBSD.org.
  - `build-iso.sh`: collects the package repository and builds the hybrid ISO with `poudriere image`.
  - `pkg-repo.sh`: publishes the signed online package repository that installed systems update from (see Releasing).
  - `live-post.sh`: turns the plain FreeBSD image into the live installer (console autologin, memory-backed `/var`, loader brand).
  - `test-bhyve.sh` and `test-qemu.sh`: unattended install tests.
  - `docs/getting-started.md`: the beginner's guide; its screenshots are in `docs/images/`.
- **[jordanhubbard/omarchy-freebsd](https://github.com/jordanhubbard/omarchy-freebsd)**: the FreeBSD layer that `x11-wm/omarchy` installs together with Omarchy:
  - `freebsdize.in`: the adaptation of Omarchy's sources, run by the port and by `daemonarchy dev link`.
  - `compat/`: stand-ins for the systemd and Linux tools Omarchy calls (`systemctl`, `uwsm`, `journalctl`, `timedatectl`, `brightnessctl`, ...).
  - `freebsd-bin/`: FreeBSD versions of commands built on pacman, `/sys`, NetworkManager or BlueZ, among them `omarchy-wifi` (wpa_supplicant) and `omarchy-bluetooth` (FreeBSD's Bluetooth stack), which feed the network and Bluetooth panels.
  - `systemd-user/`: the session's PipeWire and keyring units.
  - `seed-user`: copies Omarchy's defaults into a home on the first session (Arch does this from `/etc/skel`).
  - `polkit-omarchy.rules`: lets an active wheel session run `omarchy-wifi` and `omarchy-bluetooth` as root.
- **[jordanhubbard/daemonarchy-desktop](https://github.com/jordanhubbard/daemonarchy-desktop)**: Daemonarchy's own layer, installed by `x11-wm/daemonarchy`:
  - The artwork: `wallpaper.svg`, `wordmark.svg` (the login screen's logo), `mark.svg` (the horned "A"), `screensaver.txt`, `about.txt`.
  - The SDDM theme that reuses Omarchy's with the Daemonarchy wordmark.
  - The System > FreeBSD menu (`omarchy-menu.jsonc`) and the `daemonarchy-*` commands behind it.
  - It has no tag convention that matches the port today (last tag `v1.1.1`; the port pins a commit); see [the repositories](#the-repositories-that-make-up-daemonarchy).
- **[jordanhubbard/daemonarchy-src](https://github.com/jordanhubbard/daemonarchy-src)**: the owned FreeBSD source fork. [Owned source builds](docs/source-builds.md) describes exact-commit world/kernel/pkgbase and installer-set preparation; [the performance plan](docs/roadmap/build-performance.md) tracks complete Component execution and build-system evaluation. Development outputs do not change a published release's selection.
- **[jordanhubbard/daemonarchy-ports](https://github.com/jordanhubbard/daemonarchy-ports)** is the release ports fork; 1.5.0 uses `e84b4c4cde0d` on `main` (1.4.1 `dd277aff`, 1.3.1 `b7857842`). Releases through 1.1.1 used [jordanhubbard/freebsd-ports](https://github.com/jordanhubbard/freebsd-ports): the earlier 1.1.1 on `daemonarchy-1.1.1`, the older 1.1 candidate on `daemonarchy-1.1-package-baseline`. Upstream review does not block releases from this fork. It carries the ports:
  - `x11-wm/omarchy`: Omarchy itself, with omarchy-freebsd as a second distfile. Its `files/` holds only patches to Omarchy's own files, among them the ones that add the `FreeBSDWifi.qml` and `FreeBSDBluetooth.qml` stand-ins to the panels.
  - `x11-wm/daemonarchy`: the full desktop's dependencies, plus daemonarchy-desktop. Defaults for new users go to `share/omarchy/skel.d/daemonarchy`, which `seed-user` copies in ahead of Omarchy's.
  - The applications and tools Omarchy uses, one port each (`x11-themes/aether`, `graphics/tensaku`, `misc/ttfx`, ...), resubmitted upstream in [freebsd/freebsd-ports#640](https://github.com/freebsd/freebsd-ports/pull/640); `x11-wm/omarchy` and `x11-wm/daemonarchy` are in [#641](https://github.com/freebsd/freebsd-ports/pull/641). The earlier #630/#635 submissions were closed unmerged. The LinuxKPI header fix is [#642](https://github.com/freebsd/freebsd-ports/pull/642); review status is independent of fork qualification.
  - `x11/quickshell` carries a fix for a use-after-free in its Hyprland IPC, which is now committed upstream ([#634](https://github.com/freebsd/freebsd-ports/pull/634)).

## Working on Daemonarchy from Daemonarchy

A Daemonarchy machine can be its own development machine, much as Omarchy's repo mode works on Arch.

`daemonarchy-dev-setup` (also System > FreeBSD > Hack on Daemonarchy) clones
Omarchy at the installed version on a `daemonarchy-dev` branch,
omarchy-freebsd, daemonarchy-desktop, this repository, and the legacy
`freebsd-ports` tree into `~/src`. It then offers to link the desktop to the
Omarchy checkout. It does not install Literate AI or select the source and
ports revisions for a release.

### Check out all build inputs

For a fresh development workspace, clone the owned repositories and the
framework separately. A native build host needs sufficient space for the full
source and ports trees. Source and ports use `daemonarchy` for owned integration
and `main` for upstream tracking; a published checkout catalogue may select a
different branch at its exact release commit. The 1.5.0 catalogue selects
source `daemonarchy` and ports `main`.

```sh
mkdir -p ~/src
git clone https://github.com/jordanhubbard/daemonarchy.git ~/src/daemonarchy
git clone https://github.com/jordanhubbard/daemonarchy-src.git ~/src/daemonarchy-src
git clone https://github.com/jordanhubbard/daemonarchy-ports.git ~/src/daemonarchy-ports
git clone https://github.com/jordanhubbard/daemonarchy-desktop.git ~/src/daemonarchy-desktop
git clone https://github.com/jordanhubbard/omarchy-freebsd.git ~/src/omarchy-freebsd
git clone https://github.com/jordanhubbard/literate-ai.git ~/src/literate-ai
git clone https://github.com/basecamp/omarchy.git ~/src/omarchy
```

Read `verification/release-<version>.json` for published product, source and
ports commits. Check out the full hashes, for example `git -C
~/src/daemonarchy-src switch --detach <source-commit>`. The selected ports'
`x11-wm/daemonarchy/Makefile` pins desktop source; `x11-wm/omarchy/Makefile`
and `distinfo` pin compatibility and upstream Omarchy inputs. Select a
framework distribution whose identity matches the product's lifecycle
binding. Keep edits on review branches; detached checkouts reproduce releases.

### Literate AI and the native build

From the product checkout, use the selected framework runtime for
`litai project validate .`, `litai verify` and `litai release check`. The last
invokes the product release gate with its record and staged assets. The 1.5.0
release used native FreeBSD tools, Poudriere, signing and ISO tooling to build
the actual artifacts. A passing authority or lock check is not native build
evidence; complete framework-executed source/ports and release work is queued
for [1.5.1](docs/roadmap/release-1.5.1.md).

On an installed system, `sudo daemonarchy-checkouts src "$USER"` and
`sudo daemonarchy-checkouts ports "$USER"` materialize the release-pinned Git
trees at `/usr/src` and `/usr/ports` when those destinations are empty. The
optional packages own seed archives, while the user owns the working trees.
A future `litai` package would supply the CLI. Installing it alone would not
clone, update, regenerate or build either tree, or change installed base,
kernel or ports packages. Source and ports have their own in-place contracts
and locks; a compatible runtime can inspect them with
`litai project validate` from the chosen tree. Full Component coverage and a
common `litai-dev` build/test/package path remain open under
[DEV-001](docs/roadmap/active-work.md#dev-001-provide-an-operator-ready-native-component-development-system).

### Omarchy from a checkout

`daemonarchy dev link ~/src/omarchy` runs the desktop from your checkout after a reboot. A checkout of Omarchy is Arch-flavored, so on FreeBSD it is not run directly: the omarchy port's `freebsdize` builds the same FreeBSD tree the port installs (applying the port's patches, adding the FreeBSD versions of commands, rewriting paths and interpreters) into `~/.local/share/omarchy-dev`, and `OMARCHY_PATH` points there. While an Omarchy session runs, `daemonarchy dev sync --watch` rebuilds that tree a moment after each save; `daemonarchy dev sync` does it by hand. `daemonarchy dev unlink` goes back to the installed Omarchy.

The link also points sudo at the tree's commands (a `secure_path` in `/usr/local/etc/sudoers.d/omarchy-dev-path` that keeps FreeBSD's `/sbin`, `/bin`, and `/usr/sbin`).

If one of the port's patches stops applying to your checkout (you moved past the version the port packages), `daemonarchy dev link` and `sync` say so; refresh the patch in `~/src/freebsd-ports/x11-wm/omarchy/files`.

### The FreeBSD layer and the desktop layer

The ports fetch omarchy-freebsd and daemonarchy-desktop as tagged releases. To try your own checkout instead, let the port extract its sources, lay the checkout over them, and let it carry on:

```
cd ~/src/freebsd-ports/x11-wm/omarchy        # or x11-wm/daemonarchy
make extract
rsync -a --exclude .git ~/src/omarchy-freebsd/ "$(make -V WRKSRC_freebsd)/"
#   for daemonarchy: rsync -a --exclude .git ~/src/daemonarchy-desktop/ "$(make -V WRKSRC)/"
sudo make reinstall clean
```

`daemonarchy dev link` takes the FreeBSD commands and `freebsdize` from the installed port, so reinstall the omarchy port this way before linking to try changes to them.

### Observe native source dependencies

After pinned-tree discovery, use the native collector from this repository with
Python 3.11 or later on an unprivileged amd64 FreeBSD worker. Keep the output
outside the source tree and use a new directory for every observation:

```sh
python3 /path/to/daemonarchy/scripts/resolve-freebsd-dirdeps.py \
  --repo /path/to/daemonarchy-src --revision <full-source-commit> \
  --output /path/to/new-observation --unit bin/ls --acknowledge-evaluation
```

This evaluates trusted Makefiles, including parse-time commands, while requesting
only variables; it is not a sandbox or a build/acceptance pass. It rejects dirty
or ignored source inputs, bounds each query and the total run, retains partial
records on failure and refuses existing output directories. Omit `--unit` to seed
all amd64 dependency declarations and follow supported host/common contexts.
Missing declarations, unsupported contexts and cycles cause a nonzero result.
Run `PYTHONDONTWRITEBYTECODE=1 python3 tests/native-dirdeps.py -v` for eleven portable
refusal/graph/process checks; native observation remains a separate result.

## Isolated test-image staging

Every `build-iso.sh` invocation allocates a new private directory beneath
`ISO_STAGE_PARENT` (default `/var/tmp`) and prints its path. The parent must
already exist and be an absolute, nonsymlink directory. Failed and completed
staging trees remain for inspection; a later invocation never deletes them.
Use separate output names, output directories and native build selections too:
private staging alone does not make concurrent mutation of a poudriere jail safe.

The [1.2 test-ISO preparation](docs/testing-1.2-test-iso.md) precedes physical
qualification and is separate from final release publication.

## Setting up a build host

The product controller now pins the exact combined framework wheel from source
`e90cbadb`, recorded in `verification/native-first-binding-integration-development.json`.
It combines reviewed Standard binding with metadata-only original-source adoption;
the preceding `73311c69` checkpoint remains historical migration evidence.
Select the matching isolated installation as `FRAMEWORK_CLI` in private operator
configuration and use `"$FRAMEWORK_CLI"` for lifecycle planning and verification.
The default installed CLI and active source/ports workspace are preserved. This
configuration binding does not qualify a retained native build or produce its
missing receipt. Original-source authority is now selected through the reviewed
metadata-only `project adopt-original` flow. Actual action/input profiles and
native admission remain required. Use the explicit retained manifest/profile
`build` or `test` interface for that work; legacy harness readmission expects
legacy conversion metadata and is not an original-project initializer.

For a loader-only hardware test medium, follow
[the 1.2 test-ISO checklist](docs/testing-1.2-test-iso.md). `TEST_LOADER_BUNDLE`
selects a hash-checked EFI/Lua bundle for the live medium only. It refuses a
Secure Boot bundle and does not provision debugging keys, enable the console,
change installer sets or select the installed-system loader. Run
`python3 tests/test-loader.py -v` for its selection/refusal controls; actual image
assembly, boot and native lifecycle admission remain separate requirements.

For builds from our owned FreeBSD-CURRENT fork, start with
[owned source builds](docs/source-builds.md) and the versioned daemonarchy-src
runbook. That workflow produces development pkgbase packages and installer sets
from an exact source commit. The snapshot-based procedure below remains the
current release input path until the owned outputs pass admission, signing,
matching jail/module and VM/hardware qualification.

During source and ports development, periodically refresh the upstream tracking
refs for FreeBSD-CURRENT and ports `main`. Check again before choosing a new
diagnostic baseline, submitting a fix or qualifying a release. Review relevant
upstream commits, including LinuxKPI, NVMe, EFI, DRM ports and firmware changes,
and record the fetched revisions and the disposition of related fixes. Refresh
our development branches in isolated worktrees, preserving local patches and
skipping fixes already upstream. Pin each resulting source/ports selection and
rebuild against its matching kernel headers before native and hardware tests.
Keep the previous qualified selection available for comparisons and rollback;
fetching upstream alone is not an integrated or qualified refresh.

For pinned Git-tree discovery, run `python3 scripts/inspect-freebsd-graph.py`
with `--kind source` or `--kind ports`, `--repo`, an exact `--revision`, and a new
`--output` path outside the inspected repository. A ports object store can be
cloned with `--filter=blob:none --no-checkout`; discovery needs its tree objects,
not Makefile evaluation. Run `PYTHONDONTWRITEBYTECODE=1 python3 tests/native-tree-discovery.py -v`
for the portable refusal tests. Discovery outputs are not canonical catalogs,
complete dependency graphs, pkg provenance or framework receipts. See the
[Component/performance plan](docs/roadmap/build-performance.md).

You need a FreeBSD 16.0-CURRENT machine (bare metal or a VM with capacity for the selected build) with poudriere, git, and the ports tree, as root.

The 1.1.1 dependency rebuild used an isolated 20-CPU, 80-GiB VM with a 400-GiB
disk and two package builders. Smaller hosts may work with lower concurrency;
the full Chromium/CEF/LLVM dependency stack needs substantially more time and
space than a cached installer-only rebuild. Check resources before dispatching.

1. **A jail from the snapshot the image installs.** Before the next release, re-sync system sources with [FreeBSD CURRENT (`main`)](https://github.com/freebsd/freebsd-src/tree/main), select the image snapshot, and record its exact source revision. `/usr/src` offered by the installer must match that snapshot; do not fetch a moving branch at install time. Recreate/update the build jail and rebuild the selected kernel modules when moving snapshots. Cache the verified release sets first, then use those same files for the jail and ISO:

   ```
   sh scripts/cache-release-sets.sh
   poudriere jail -c -j 16amd64 -a amd64 -v 16.0-CURRENT -m tar=/var/cache/daemonarchy-iso/base.txz
   tar -xpf /var/cache/daemonarchy-iso/kernel.txz -C /usr/local/poudriere/jails/16amd64
   tar -xpf /var/cache/daemonarchy-iso/lib32.txz -C /usr/local/poudriere/jails/16amd64
   ```

   Populate the jail's `/usr/src` from that same source revision before building
   kernel modules. Include `lib32` before the first bulk run: dependencies such
   as LLVM need its 32-bit libraries, and adding it later changes GCC's default
   multilib option and invalidates cached compiler/dependency packages.

   On ZFS, Poudriere clones the jail's `@clean` snapshot, which jail creation
   recorded before those additions. Retain that initial snapshot under another
   name and recreate `@clean` from the completed jail before starting a build.
   Verify that the snapshot itself contains `/boot/kernel/kernel`,
   `/usr/lib32/libc.so.7` and the selected `/usr/src/sys/sys/param.h`; checking
   only the live jail directory does not establish what its build clones use.

2. **A ports tree pinned to the official package set.** Before the next release, refresh [the fork's `omarchy` branch](https://github.com/jordanhubbard/freebsd-ports/tree/omarchy) from [upstream FreeBSD ports](https://github.com/freebsd/freebsd-ports), preserving and testing the Daemonarchy changes. 1.3.1 selects daemonarchy-ports `b7857842`, recorded in [its release notes](docs/release-1.3.1.md); the earlier 1.1.1 used `daemonarchy-1.1.1` ([record](docs/testing-1.1.1.md)) and the 1.1 candidate `daemonarchy-1.1-package-baseline`. When the selected tip is newer than the official binary baseline, as it was from 1.1.1 on, mismatched dependencies must also be rebuilt and published in the release's versioned feed. Keep the selected integration fixed during qualification. Matching pkg.FreeBSD.org's `latest` baseline avoids rebuilding large dependency stacks; moving beyond it requires the versioned rebuilt-dependency publication procedure below. The official baseline is the newest `ports_top_git_hash` annotation across the set's packages. Builds are incremental, so one package's annotation can be older than the set:

   ```
   mkdir -p /tmp/pq/db /tmp/pq/repos
   printf 'FreeBSD: { url: "pkg+https://pkg.FreeBSD.org/FreeBSD:16:amd64/latest", mirror_type: "srv", signature_type: "fingerprints", fingerprints: "/usr/share/keys/pkg", enabled: yes }\n' >/tmp/pq/repos/FreeBSD.conf
   P="pkg -o PKG_DBDIR=/tmp/pq/db -o REPOS_DIR=/tmp/pq/repos -o ABI=FreeBSD:16:amd64 -o OSVERSION=1600026"
   $P update -q
   $P rquery -a '%At=%Av' | sed -n 's/^ports_top_git_hash=//p' | sort -u
   ```

   Check out the newest of those commits and apply the Daemonarchy-specific commits from `origin/omarchy` in order, skipping changes already upstream. Review that list after each sync; it must not include upstream merge commits. Register the resulting tree with poudriere:

   ```
   git clone --branch omarchy https://github.com/jordanhubbard/freebsd-ports.git /usr/local/poudriere/ports/omarchyiso
   cd /usr/local/poudriere/ports/omarchyiso
   git remote add upstream https://github.com/freebsd/freebsd-ports.git
   git fetch upstream main
   git checkout -b omarchy-iso <commit>
   git cherry-pick <daemonarchy-commit-1> <daemonarchy-commit-2> # reviewed list, in order
   poudriere ports -c -p omarchyiso -m null -M /usr/local/poudriere/ports/omarchyiso
   ```

3. **poudriere settings** (`/usr/local/etc/poudriere.d/omarchyiso-poudriere.conf`): build the kernel modules for the jail's kernel instead of fetching the package builders' copies, which target a different kernel:

   ```
   PACKAGE_FETCH_BLACKLIST="drm-*-kmod gpu-firmware-* wifi-firmware-* nvidia-* linux-nvidia-libs"
   PACKAGE_FETCH_URL="http://pkg.FreeBSD.org/\${ABI}"
   DISTFILES_CACHE=/usr/ports/distfiles
   ```

4. **Build the packages.** List the origins in `ISO_ORIGINS` and `LIVE_ORIGINS` in `origins.sh` in a file (`LIVE_ORIGINS` holds what only the live desktop root needs, such as `security/sudo`; it is not copied into the ISO repository), and bulk-build with `-b latest`. Poudriere fetches eligible official dependencies and builds incompatible or missing ones against the selected jail:

   ```
   poudriere bulk -j 16amd64 -p omarchyiso -b latest -t -f omarchyiso-ports.list
   ```

   A refresh ahead of the official binary baseline can require hundreds of builds, including compilers and browsers. Preserve caches and logs; elapsed time alone is not evidence that a build stalled. An installer-only rebuild can reuse the qualified package set.

5. **Build the image:**

   ```
   ./build-iso.sh
   ```

   The image is named from the repository's `VERSION` file (`scripts/version.py`): `daemonarchy-<version>-<arch>.iso`, for example `daemonarchy-1.5.1-amd64.iso` (published xz-compressed as `.iso.xz`). Set `NAME` to override. `build-iso.sh` refuses a `VERSION` that is not `X.Y.Z`.

   The image and its `.sha256` land in `/usr/local/poudriere/data/images`.

   The live installer omits the base development toolchain, C/C++ headers,
   static libraries and compiler resources using `scripts/live-image-excludes`.
   Its shells, networking, storage and rescue tools remain available. These
   exclusions apply only to the live root: `base.txz` and `kernel.txz` remain
   intact, so the installed system retains its compiler, headers and libraries.
   Optional ports/source checkout packages are fetched separately; only their
   small catalogue is on the ISO. Releases publish the image as `.iso.xz`, so
   GitHub's 2 GiB per-asset limit applies to that compressed asset: the build
   rejects an `.iso.xz` at or above 2 GiB before generating its checksum. The
   raw ISO keeps a 3.5 GiB (3,758,096,384-byte) budget so it still fits a 4 GB
   USB stick, checked before its own checksum. Run
   `bash tests/live-image-budget.sh` to check the exclusions and both size
   boundaries. The build log records the live `/usr/local` size before and
   after the live desktop trim, which the same test exercises.
   On FreeBSD, `sudo sh tests/live-image-runtime.sh <iso>` mounts the image
   read-only, checks required live commands and payloads (including the live
   desktop's tools, startup wiring and GTK runtime), and resolves the
   dynamic dependencies of every retained ELF program and library. It uses
   and detaches its own temporary memory-disk device. Follow this with a VM
   boot check; the dependency audit does not qualify installation or hardware.

   For development images, set `NAME` to a distinct preview filename and
   `PREVIEW_LABEL` to a short description. The installer welcome screen shows
   that label alongside the actual desktop package version.
   The [private MacBook Wi-Fi preview](docs/testing-macbookpro16-1-wifi-preview-20261022.md)
   is an operator-only hardware image assembled from the published 1.1.1 ISO,
   with a kernel-matched diagnostic module and board firmware staged outside
   Git. Its firmware source declares an unknown license; keep the image private
   until redistribution rights or a supported acquisition path are established.
   The EFI timer revision stages a verified loader in the live `/boot/loader.efi`
   and EFI boot image. Its matching SHA-256 is staged as
   `macbook-efi-timer-loader.sha256` beside the offline repository; `install`
   refuses to copy a mismatched loader into a MacBook target.
   The diagnostic scan-parser change is retained as
   `patches/brcmfmac/bcm4364-security-ie-bounds.patch`; its input `src/scan.c`
   SHA-256 is recorded in the hardware test note. Build the resulting module
   on the native FreeBSD worker against the exact ISO kernel sources, then
   verify the staged module hash before authoring the image.

   For MacBookPro16,1 firmware development, `scripts/import-apple-bcm4364-firmware.py`
   can download the pinned Sonoma recovery image from Apple's recovery service
   or read an operator-supplied `BaseSystem.dmg`. For example, with Python 3 and
   `7z` installed, run on FreeBSD
   `python3.12 scripts/import-apple-bcm4364-firmware.py --download --model MacBookPro16,1 --destination /private/firmware-import`.
   Replace `--download` with `--image /path/to/BaseSystem.dmg` for local media.
   The tool verifies the exact image and four board-file hashes before creating
   the fresh private destination. Recheck a staged import with
   `python3.12 scripts/import-apple-bcm4364-firmware.py --verify-stage --model MacBookPro16,1 --destination /private/firmware-import`.
   It records a provenance JSON file and does not add firmware to Git or a
   redistributable ISO. The MacBook installer now offers the pinned Apple
   download over Ethernet, an operator-supplied recovery image on mounted
   media, or an already verified private stage before the network screen. It
   imports into a private live stage, verifies the four files, attaches the
   radio, and carries the files and provenance into the target. An unattended
   MacBook install defaults to the download;
   `apple_firmware_image=/absolute/path/BaseSystem.dmg` selects local media.
   Acquisition and verification against the signed boot inventories occur
   before disk changes. The live temporary filesystem needs at least 817 MiB
   free while the image is checked. The signed boot manifest must admit the
   exact firmware hashes before a verified-boot target can receive them.
   The driver, module inventory, physical reboot and Wi-Fi traffic still
   require qualification on the MacBook; this candidate is not a release image.

### Persistent authoring caches

Keep the following directories on persistent storage on the ISO build host.
They are reused by anyone following this build workflow, including authors
running it inside a VM; retain its disk or mount persistent cache storage when
replacing the VM.

| Build input | Persistent location | Reuse |
| --- | --- | --- |
| Port source archives | `DISTFILES_CACHE`, above `/usr/ports/distfiles` | Ports reuse downloaded distfiles and verify them against `distinfo`. |
| Official dependency packages | `/usr/local/poudriere/data/packages/$JAIL-$PTREE/.pkg-cache` and the package repository | With `-b latest`, poudriere fetches eligible packages into its cache and links them into the repository. |
| Built packages | `/usr/local/poudriere/data/packages/$JAIL-$PTREE` | Poudriere checks existing packages and builds only missing or invalidated ones. |
| FreeBSD release sets | `SET_CACHE_DIR`, default `/var/cache/daemonarchy-iso` | `cache-release-sets.sh` and `build-iso.sh` share `MANIFEST`, `base.txz`, `kernel.txz`, and `lib32.txz`. |

Repeat the bulk and image commands with the same jail, ports-tree name and cache
paths. An installer-only change normally needs just `build-iso.sh`; it reuses
the package repository and release sets. Poudriere invalidates packages when
versions, options or dependencies change. Kernel-bound packages must be rebuilt
for a new snapshot even when a cached package has a compatible-looking ABI.

The release-set helper hashes each cached archive against the retained
`MANIFEST`. A valid archive is reused without contacting the snapshot server.
A missing or damaged archive is downloaded to a temporary file and replaces
the cache entry only after its checksum passes. A failed or partial download
does not replace the previous file. The image build also checks the jail's
FreeBSD version and the catalogue's source revision against the kernel set.

To put sets on another volume or retain separate snapshots, use the same
override for cache preparation and image construction:

```sh
export SET_CACHE_DIR=/build-cache/daemonarchy/sets/<selected-source-revision>
export SNAPSHOT_URL=https://download.freebsd.org/snapshots/amd64/16.0-CURRENT
sh scripts/cache-release-sets.sh
# Create the jail from "$SET_CACHE_DIR/base.txz" and extract its kernel/lib32.
JAIL=16amd64 PTREE=omarchyiso sh build-iso.sh
```

On a worker with a separate Poudriere configuration directory, set
`POUDRIERE_ETC=/path/to/poudriere-etc` for `build-iso.sh` so its jail query and
image command use the same configuration as the package bulk. If that
configuration sets its own `POUDRIERE_DATA`, pass the same value to
`build-iso.sh`, which reads the package repository from
`$POUDRIERE_DATA/packages/$JAIL-$PTREE` (default `/usr/local/poudriere/data`).

For source-built sets such as 1.1.1, populate this directory from the exact qualified build, including its MANIFEST, rather than fetching a newer daily snapshot. The moving snapshot URL is consulted only for missing inputs. Select a new
cache directory for a new snapshot so an older retained `MANIFEST` cannot be
mistaken for the new selection. Preserve poudriere's repository structure,
including `.latest` and any `.building` directory left by an interrupted bulk
run; poudriere can resume using its completed packages. Its cache management
may prune obsolete entries, so these directories are caches rather than release
archives. Retain final ISOs, checksums and published checkout payloads separately.

Fresh installer test VMs currently have independent package caches. The
authoring caches above speed package and ISO construction; sharing downloads
between those fresh test installations is a separate harness improvement.
Run `sh tests/release-set-cache.sh` on FreeBSD to exercise initial fetching,
offline reuse, damaged-entry repair and rejection of a corrupt replacement.

## Changing things

### The installer

The installer flow lives in `overlay/`, primarily as Bash helpers. An installer-only change needs a new image (`./build-iso.sh`) and runtime validation; it can reuse the already qualified package set.

For 1.4.1 performance baselines, copy the terminal target's
`/var/db/daemonarchy/install` directory and
`/var/log/daemonarchy-install.log`, then create a reviewed context that uses the
`daemonarchy/installer-measurement-context@1` schema and run:

```sh
python3 scripts/installer-measurements.py \
  --diagnostics evidence/install \
  --log evidence/daemonarchy-install.log \
  --context evidence/context.json \
  --output evidence/measurement.json
```

When the target repository databases and an installed `pkg query` manifest are
retained, derive the selection and context rather than transcribing package
counts or sizes:

```sh
python3 scripts/installer-baseline-context.py \
  --image daemonarchy.iso \
  --package-evidence evidence/guest-install-evidence.tar \
  --installed-manifest evidence/installed-package-manifest.txt \
  --target evidence/target.json \
  --inventory-output evidence/package-selection.json \
  --context-output evidence/context.json
```

Use `--replace-catalogue ID=packagesite.pkg` when a post-install update replaced
the repository database that actually supplied the install, and
`--repository-alias INSTALLED=SOURCE` only for a reviewed repository annotation
performed by the installer. Both choices become part of the selection identity.
The builder refuses packages absent from the retained catalogues and ambiguous
archive identities. A historical run may record `link_measurement: unknown` and
`link_mbps: null`; its timing remains useful, but it is not an equivalent-link
acceptance baseline.

The context binds the exact image and package-selection/catalogue identities,
image and package bytes, worker identity, machine/storage class, measured link
speed (or an explicit historical unknown) and whether package bytes came from
the network, ISO, attached media or a mixture. The output is create-only and
content-identified. It retains terminal failure as failure and refuses incomplete
success, repeated/backward stage clocks or ambiguous context. This is comparable
timing evidence, not installation or release acceptance; keep the native log,
integrity diagnostics and desktop acceptance separately.

- **The install screen** can be tried without an install: `dashboard` draws from a log file, so feed it one. Run it in a 160x50 terminal (the console's size) with `ISO_SHARE` pointing at a directory holding `logo.txt`, and append `@@phase <name>` lines, `Number of packages to be fetched: N`, `Fetching <pkg>: ... done`, and `[ n/N] Installing <pkg>...` lines to the log; it exits with the number written to the status file.
- **`install`** reads its answers from `$DAEMONARCHY_INSTALL_CONF`; the keys are what `configurator`'s `write_install_conf` writes. An unattended install takes the same file from a FAT drive labelled `CIDATA`, which is how both test scripts run.
- **`configurator`** sources Omarchy's setup form from the `omarchy` package at build time (`build-iso.sh` extracts it), so the account, hostname, and timezone questions follow Omarchy's.

The candidate ISO takes `if_brcmfmac-kmod` from the selected ports tree and
installs that package only on MacBookPro16,1 targets. The live installer checks
that its module bytes match the installed package, then locks the target
package to the selected kernel. For a private preview, the verified B3 firmware
can still be supplied under `$LIVE_EXTRA_OVERLAY/boot/firmware/` as
`brcmfmac4364b3-pcie.{bin,txt,clm_blob,txcap_blob}`. Set
`LIVE_EXTRA_OVERLAY` when running `build-iso.sh`; the live system loads the
driver at boot when the firmware is present. The public image instead imports
the board files from Apple before loading the driver. Test a fresh boot, Wi-Fi
join, DHCP, traffic and reconnect before calling the image qualified. Keep
firmware-bearing overlays and their ISOs private while redistribution rights
are unverified. The FreeBSD driver port uses the ISC-licensed upstream source;
Apple firmware has separate terms.

### The live desktop

The loader's **Try Daemonarchy (live desktop)** entry (the disk stays untouched
until an installation is confirmed), added by `brand-daemonarchy.lua` only when
the image's `loader.conf` sets `daemonarchy_live_media`, sets the
`daemonarchy_live` kenv. The default entry still boots the text installer. The
same brand file hides the developer entries **Boot trace** and **Network
debugging** unless `loader.conf` sets `daemonarchy_debug_menu="YES"` (the
hardware trace image sets `boottrace_stick="YES"`, which shows them too), so the
menu ends inside its frame; `lua5.4 tests/loader-live-menu.lua` checks this
against the real `menu.lua` and `drawer.lua` kept in `tests/fixtures/loader-lua`. The pieces, all in
`overlay/usr/local/libexec/daemonarchy-installer/`:

- **`live-service`** (installed as `/etc/rc.d/daemonarchy_live`) copies `/etc`,
  `/usr/local/etc`, `/root` and `/home` each into its own tmpfs, the way
  FreeBSD's `rc.initdiskless` does. `/var` (with pkg's database) and `/tmp`
  are already tmpfs; the rest of `/usr/local` stays the read-only ISO.
- **`live-gpu`** reuses the installer's `gpu_select` and exact `gpu-packages`
  manifest. It extracts the DRM and firmware kernel modules from the ISO
  repository into `/live/modules`, appends that directory to
  `kern.module_path`, and runs `kldxref` there, so `/boot/modules` and its
  `linker.hints` are never rewritten. NVIDIA's userspace driver is added with
  `pkg add -I -M` after a tmpfs is mounted with `-o union` on each existing
  `/usr/local` directory that receives a new file. That layer can add names but
  cannot replace ISO files, so `live-gpu` refuses a package that would replace
  one and names the file.
- **`live-session`** runs from root's ttyv0 login before the text installer:
  it loads the GPU driver, starts `seatd` and runs Hyprland as the `live`
  account (created when the image is built) through `live-desktop`. When the
  desktop ends or cannot start, ttyv0 continues into the text installer; the
  live fallback never starts a CIDATA unattended install. Set
  `daemonarchy_live_test=compositor-failure` at the loader prompt to exercise
  the fallback with working graphics.
- **`live-installer`** (GTK 3 through PyGObject) is the graphical front-end.
  It sends every privileged request to **`live-backend`**, which the `live`
  account may run as root through `sudo` and nothing else. The backend sources
  `configurator`, whose screens only run when it is executed, so both paths
  share the questions' rules, disk inventory, network helpers and
  `write_install_conf`. Its network page runs `network-bringup`'s pipeline
  and steps with the configurator's adoption rules (`network_bringup_adopt`,
  `network_recheck`), shows each step's report, and offers the same primary
  interface override, DNS server entry and clock rule (network time first,
  then a hand-set UTC time that must pass `nb_clock_status`). Where the text
  installer would prompt, the backend records `need=dns|clock|wifi` and the
  page asks; `tests/live-backend.sh` checks that both front-ends reach the
  same decisions. It starts the same `install` engine with the same log
  and result file, and the front-end renders them with
  `progress-dashboard.py`'s parser.

The live path does not use unionfs. A probe that mounted `mount_unionfs` over
`/etc` of the 1.3.1 ISO on a FreeBSD 16-CURRENT build host stopped that host
while `pw` rewrote the password database (a rename into the union). The host
needed a power cycle; whether it hung or panicked awaits its crash dump. The
controller test `tests/live-desktop.sh` fails if any live-path script uses
unionfs. Plain `-o union` mounts are used only where files are added.

`bash tests/live-desktop.sh`, `bash tests/live-backend.sh`,
`python3 tests/live-installer.py` and `lua5.4 tests/loader-live-menu.lua` run
on any host with stubs and do not qualify FreeBSD mounts or graphics. The
native checks still required on an exact image:

- `live-service`'s tmpfs copies at boot, including `/etc` with `pw useradd`
  and `pwd_mkdb` afterwards, and `/usr/local/etc/sudoers.d` permissions.
- `kldxref` and firmware loading from `/live/modules` for amdgpu, i915kms and
  virtio_gpu_drm, and NVIDIA userspace addition on `-o union` layers,
  including whether any package file would replace an ISO file.
- seatd and Hyprland started from root's ttyv0 login through `su -l live`.
- The graphical installation, before/after disk digests and the TUI fallback
  (see the LIVE-001 evidence items in the active queue).

### The ports

Work on a review branch based on the exact integration commit in [ROADMAP.md](ROADMAP.md). For 1.5.0 this is daemonarchy-ports `main` at `e84b4c4cde0d`, pinned in [its release notes](docs/release-1.5.0.md) (1.3.1 used `b7857842`, in [its notes](docs/release-1.3.1.md)); verify that poudriere uses the matching tree and snapshot jail before rebuilding.

- `poudriere testport -j 16amd64 -p <tree> -o <origin>` checks a port in a clean jail: stage-qa, the plist, install, and deinstall. Use it rather than `make stage-qa` as root on the host, which installs the port's dependencies onto the host.
- To try a change on a running Daemonarchy desktop, `make reinstall` the port there; `seed-user --force` re-copies the defaults into the home (it never overwrites a file you have).
- Pin each reviewed omarchy-freebsd or daemonarchy-desktop source change to an immutable tag or full commit in its port (`GH_TUPLE` in `x11-wm/omarchy`, `DISTVERSION` in `x11-wm/daemonarchy`), and run `make makesum`.
- Bump `PORTREVISION` whenever a package's contents change: poudriere rebuilds on version changes, not on file changes, so an unbumped port keeps its old package.
- Review and merge against the selected integration branch, pin its merged commit, then run native `poudriere testport` and rebuild the combined packages (step 4 above). Keep the matching official-package baseline; do not merge a moving ports tip into the qualified tree.

### The artwork

The wallpaper, wordmark, and mark are SVG in daemonarchy-desktop; the `x11-wm/daemonarchy` port renders the wallpaper to a 3840x2160 JPEG and the wordmark to the login screen's PNG with `rsvg-convert` at build time. Preview an edit with `rsvg-convert -w 1920 wallpaper.svg -o preview.png`. `about.txt` (the About screen's art) was made from `mark.svg` with Omarchy's own `omarchy-transcode-ascii`, and `screensaver.txt` is the same wordmark the installer shows.

Daemonarchy's artwork is original: keep the FreeBSD and Arch Linux logos out of it, and keep Daemonarchy's identity in daemonarchy-desktop rather than in Omarchy's files or omarchy-freebsd.

## Testing

The unattended harnesses check the installed system: the account and its
`wheel`, `operator`, `video`, and `audio` groups, SDDM's user, session, and theme,
sshd, Avahi, mDNS lookups, DHCP, and the Daemonarchy defaults. These SSH checks
do not qualify a graphical desktop. Hyprland requires a working DRM renderer;
the new VirtIO DRM/VirGL candidate and its separate graphical checks are
described in [the VM graphics record](docs/testing-1.1-vm-graphics.md). Preview.13
does not contain that driver integration.

- **`test-bhyve.sh <iso>`** on a FreeBSD host with VT-x or AMD-V, as root, with `edk2-bhyve` installed. It reads the installed disk directly after the install. `NET=nat` (the default, with pf and dnsmasq) or `NET=bridge` (onto the host's network, using the LAN's DHCP); `test-bhyve.sh --cleanup` undoes either. The guest's memory is wired (`MEM`, default 3G) so a busy host cannot swap it out: leave the host at least that much free, or lower `MEM`.
- **`test-qemu.sh <iso>`** anywhere QEMU runs, without root: it logs in over SSH and checks from inside. On a non-x86 host the guest is emulated, and an install takes two to three hours.

For the 1.1 BIOS work, run `BOOT_MODE=bios ./test-qemu.sh <iso>` and
`BOOT_MODE=uefi OVMF=/path/to/OVMF.fd ./test-qemu.sh <iso>` with separate
`WORK` directories. UEFI remains the default. Both runs check the firmware
mode reported by the installed kernel. `sudo bash tests/disk-layout.sh` on
FreeBSD checks the partition layout and actual BIOS bootcode on temporary
memory disks with 512-byte and 4 KiB sectors; it does not prove bootability.
The added BIOS partition is p4, in the alignment gap before the EFI partition,
so the existing EFI, swap, and ZFS partition numbers remain unchanged.

### Boot-environment mount policy

Boot-environment roots, including the original `ROOT/default`, must use
`canmount=noauto`. The installer explicitly mounts that first root before
writing into it. An inactive sibling with automatic mounting enabled can cover
the selected boot environment at `/`, including its mounted `/dev`. A cloned
environment's own `noauto` property does not protect it from that sibling.
For an older installation, inspect `zfs list -o name,canmount,mounted,mountpoint`
for the pool's boot environments before migration and correct each boot root
with mountpoint `/` to `canmount=noauto`; preserve unrelated datasets. Changing
that property does not unmount an already mounted root.

Run `sudo bash tests/boot-environment-mounts.sh` on FreeBSD. It executes the
actual installer root-creation commands in its own temporary memory-disk pool,
checks the initial explicit mount, and switches to a cloned root while keeping
the original inactive and devfs visible. It never runs global `zfs mount -a`
or changes another pool.

### BIOS and shared-disk fixtures

For a faster BIOS boot-chain check, run
`sudo bash tests/bios-boot-image.sh /new/test-directory /usr/local/poudriere/jails/16amd64`
on FreeBSD. It creates a disposable ZFS disk containing that snapshot's boot
files. Boot `disk.img` in QEMU with SeaBIOS and `-serial stdio`; reaching the
FreeBSD loader prompt checks the BIOS-to-ZFS-loader chain. This deliberately
does not install packages or qualify the complete installed desktop.

Shared-disk development is covered by `sudo bash tests/shared-disk.sh` on a
headless FreeBSD worker. It allocates its own disposable memory disks and tests
partition/EFI preservation and pre-write rejection. See the
[partition preview guide](docs/testing-1.1-partitions.md) for scope and physical
acceptance. A shared-disk unattended config must explicitly set
`install_mode=partition` with `partition_index`, or `install_mode=free_space`
with `free_start` (sector offset) and `install_size_mib`; both also require
`efi_index` and a current `disk_snapshot` from `disk_fingerprint`. The interactive
configurator writes these values. Omitting the mode retains the original
whole-disk unattended behavior; never omit it when preserving another OS.

Both send the installer's log to the guest's serial port, so a stalled install leaves a trail.

Set `INSTALL_PORTS=true INSTALL_SRC=true` on either harness to exercise both
optional live checkouts. After reboot, the checks run as the installed user and
verify ownership, clean Git status, exact catalogue revisions, tracking branches
and depth-1 history. The source revision must match the installed kernel.
Leave either option unset to check its default-off behavior. Use separate
`WORK` directories for each run. The bhyve harness now verifies SSH login after
reboot and shuts down the guest after checking it; bridge mode requires
`GUEST_IP`. Its NAT mode discovers the address from its own DHCP lease file.
Run `test-bhyve.sh --cleanup` with the same `WORK`, `VM`, `TAP` and `BRIDGE`
settings afterwards to remove the test network.

On real hardware, the install log is `/tmp/daemonarchy-install.log` on the live system.
Development installs also stream it to the target's
`/var/log/daemonarchy-install.log`, retain installation state and kernel
snapshots under `/var/db/daemonarchy/install`, and install recovery before
the desktop package transaction. See the [rescue console guide](docs/rescue-console.md)
for the password gate, boot monitor, interrupted-install behavior and tests.

NVIDIA installation enables both `linux` and `linux64` in the live kernel
before disk writes. The `linux_base` pre-install script checks
`kern.features.linux64` on that running kernel, including when using `pkg -r`.
Deferring Linux compatibility until the installed system boots is too late.
The cache repair step also repeats Linux ldconfig/GIO setup inside the target.
On an older installer, `kldload linux64` from its root shell enables the missing
ABI; do not rerun the whole installer over an existing target merely to retry
the package transaction.

CUDA/toolkit and cudalab installation are withheld in the current release.
`cuda_options_prepare` rejects `install_cuda=true` before disk writes, including
unattended installation. Their development scripts and portable tests remain
in the tree, but the earlier RTX 4090 driver-API result does not qualify the
complete toolkit, Unified Memory or cudalab. See the [application policy](docs/freebsd-application-policy.md)
and [retained hardware results](docs/testing-1.1-hardware-observations.md).
Desktop NVIDIA driver installation remains separate from this disabled option.

## Remote debugging on a test machine

The development installer provides a root debug shell and a separately enabled,
console-approved SSH listener. Opening either does not start installation or
choose a target disk. See the [remote debug guide](docs/remote-agent-debug.md)
for the full operator handoff and the [rescue console guide](docs/rescue-console.md)
for recovery after an interrupted installation or failed graphical startup.

### Open the shell and establish networking

At the USB welcome screen, choose **Remote agent debug**. The network screen
also offers **Open debug shell**. Both open a local shell even without a working
network. `help` or `remote-debug help` prints the available commands; `exit`
returns to the screen that opened it.

Start by identifying the hardware and network interfaces:

```sh
kenv smbios.system.product
pciconf -lv
usbconfig
ifconfig -a
sysctl net.wlan.devices
route -n get default
```

Use Ethernet initially when available. `dhclient ue0` requests an address on
that interface; substitute the name actually shown by `ifconfig`. Wi-Fi can be
configured through the installer's network form or with FreeBSD's
`wpa_supplicant` and `dhclient`. An associated wireless interface, a DHCP address,
a default route and working DNS are separate checks. `wpa_cli -i wlan0 status`
shows authentication state without printing the configured password. Do not
print or attach the supplicant configuration, which contains credentials.

Check package-server access with a bounded probe:

```sh
timeout 8 fetch -T 5 -o /dev/null https://pkg.FreeBSD.org/
```

The outer timeout also bounds DNS resolution. A usable LAN address allows
remote debugging even when internet access, DNS or HTTPS is failing. Inspect
`/etc/resolv.conf`, the DHCP lease and the system date before changing network
settings. If the debug connection itself uses Wi-Fi, restarting that interface
interrupts access; arrange a local operator or an alternate connection first.

### Enable access and pair the agent

At the physical console, run `remote-debug listen` for port 2222, or
`remote-debug listen 2207` for another port. Confirm the enable prompt. The
screen shows usable IPv4 addresses and a freshly generated server fingerprint.
The listener requires FreeBSD, an unlocked root account and a usable address.
The shell alone does not enable it.

On the agent's machine, create a temporary session key and show its fingerprint
to the operator:

```sh
pair_dir=$(mktemp -d)
ssh-keygen -q -t ed25519 -N '' -f "$pair_dir/operator"
ssh-keygen -l -f "$pair_dir/operator.pub"
ssh -i "$pair_dir/operator" -o IdentitiesOnly=yes \
  -o UserKnownHostsFile="$pair_dir/known_hosts" \
  -p 2222 root@MACHINE_IP
```

Replace `MACHINE_IP` and the port with the displayed values. Compare the server
fingerprint before accepting its host key. The operator then compares the
agent-key fingerprint on the local console and types `y` only for that key.
Authentication can wait up to two minutes for this approval. A rejected key
stays rejected until the listener is stopped and restarted. Reuse the approved
key for subsequent SSH and SCP commands in this session (`scp` uses uppercase
`-P` for the port).

The approved connection is a root shell. Start with read-only hardware, network
and disk inventory. Installation remains a separate action requiring an agreed
target disk or partition. To operate the installer forms remotely, use
`ssh -t` and `/usr/local/libexec/daemonarchy-installer/launch`.

### Collect evidence and keep the console readable

Capture `dmesg -a` before changing verbosity. A diagnostic preview can enable
verbose boot for filming early probes; kernel and driver messages can then
overwrite an interactive screen. For the current boot, use:

```sh
dmesg -a > /tmp/daemonarchy-debug-kernel.log
sysctl debug.bootverbose=0
sysctl kern.consmute=1
```

Kernel messages remain available through `dmesg`. Restore console output with
`sysctl kern.consmute=0` before trying to capture a panic on screen. These are
runtime settings; they do not change the installed system's loader settings.
Some driver warnings are independent of verbose boot, so reducing
`debug.bootverbose` alone may not stop them.

Installation output is `/tmp/daemonarchy-install.log` on the live system when
an installation has started. Development installations also retain
`/var/log/daemonarchy-install.log` and `/var/db/daemonarchy/install` on the
target. The active debug server's log is
`/var/db/daemonarchy/remote-debug/sshd.log`; retrieve it before stopping the
listener. Keep passwords, private keys and wireless credential files out of
shared reports.

### Finish or reconnect

The console announces the first authenticated connection. During the task, the
agent should send brief, non-sensitive activity updates from its SSH connection:

```sh
daemonarchy-debug activity 'Checking Wi-Fi connectivity'
daemonarchy-debug done
```

The first command updates the local console without streaming commands or their
output. The second explicitly says that debugging is complete and it is OK to
stop the session. A short SSH command closing its connection does not mean the
overall task has finished. Completion itself leaves remote access enabled until
the operator stops the listener. Older images, including preview.13, lack this
feedback and require the agent to communicate these states directly.

Once the agent reports completion, press **Enter** or **Ctrl-C** in the local
listener console. This closes its listener and SSH connections, deletes session
host keys and approvals, and returns to the debug shell. In current development
helpers, reboot preserves an installed-system grant and its host fingerprint.
The recovery console resumes that approved listener without fresh confirmation;
its background mode accepts only previously approved keys. A stale listener can
be resumed directly without Unpair. Explicit `daemonarchy-debug unpair` revokes
both active and stale grants. Older 1.1.1 helpers used volatile approvals and
required a new pairing after reboot. Stopping access does not undo agent changes.

Run `bash tests/remote-debug-progress.sh` for portable state/command checks and
`sudo bash tests/remote-debug-session.sh` on FreeBSD for real SSH rejection,
approval, console feedback, reconnect, SFTP and stop/cleanup checks. The native
test uses an isolated temporary server on port 23451 (`DEBUG_TEST_PORT` overrides
it) and does not change the normal SSH configuration.

New installed systems expose the same commands through `daemonarchy-debug`
(`daemonarchy-debug shell`, `listen`, `resume`, or `help`). No listener starts
without prior console opt-in. A retained debugging grant resumes across reboots;
normal SSH configuration and live-USB-to-target key isolation remain separate.
`sudo bash tests/remote-debug-reboot.sh` exercises retained approval, stable host
pinning, legacy listener adoption, reused PIDs, repeated resumption and revocation
on an isolated server (default port 23452).
`sudo bash tests/remote-debug-background.sh` checks a listener kept in the
background through the installation (`listen` then `b`, or `background`): it
survives its console view and the console's Ctrl-C and hangups, new agents are
approved or denied with `pending`/`approve`/`deny` without a second virtual
console, a later `listen` attaches, and `stop` revokes it (default port 23461).

### Install screen

`PYTHONDONTWRITEBYTECODE=1 python3 tests/installer-progress.py` runs the install
screen's model, rendering, PTY and real tmux checks (the tmux cases skip without
tmux). On FreeBSD with `/usr/src`, `python3 tests/vt-console-colors.py` builds
sys/teken and checks how vt(4) draws the screen's real output, directly and
through tmux; set `VT_RENDER_OUT=DIR` to keep HTML renderings.
`scripts/installer-visuals-demo.py` records a replay of an install log through
the real screen as an asciinema cast; see docs/installer-progress.md.

### Continuous diagnostics

The diagnostics path (since 1.1.1) provides bounded read-only `daemonarchy-debug snapshot`
and `observe` output, with private, size-limited target logs. An approved
controller can retain the stream off-target using `scripts/capture-remote-debug.py`
and its existing host-key-pinned SSH wrapper. See the [continuous diagnostics
contract](docs/remote-agent-debug.md#continuous-diagnostics) for exact commands,
retention and privacy limits. It reports when console-buffer access is unavailable;
SSH diagnostics cannot reconstruct probes from before networking or survive a
hard reset as a live connection. Loader/early-kernel network debugging is
1.4 work ([plan](docs/roadmap/release-1.4.0.md)); no published release through 1.5.0
includes a qualified early-kernel network debugger.

### When the screen or keyboard is unusable

Use the guide's [private headless rescue procedure](docs/remote-agent-debug.md#keyboard-free-rescue-image)
to build a separate USB image with one preauthorized operator public key.
That mode uses Ethernet DHCP and a dedicated SSH server on port 2222, blocks
T2 BCE and desktop GPU autoloading, and ignores unattended installation media.
Keep the overlay and image private: they contain a rescue server private key.
The operator's private key stays on the agent's machine. This mode provides
access for diagnosis; it does not qualify blocked drivers or the desktop.

On an installed system, the loader setting `set daemonarchy_rescue=YES` followed
by `boot` skips the desktop GPU service and SDDM. Configured networking and SSH
can start first. This does not enable normal SSH if it was declined at install
time, or prevent unrelated device-driver panics.

Portable prompt/address tests are `bash tests/remote-debug-cli.sh` and
`bash tests/remote-debug-network.sh`. Native connection, approval, rejection,
custom-port, reconnect and shutdown evidence belongs in the
[remote debug validation record](docs/testing-1.1-remote-debug.md).

## Hardware bring-up trace image

For the planned 1.6 workflow, start with
[default installation tracing and target-specific image recipes](docs/roadmap/default-install-tracing.md).
New hardware should be described to a coding LLM with its exact model, firmware,
boot chain and symptoms, using the returned hwtrace volume to guide the next
image. Normal users must receive automatic tracing on standard installation
media; they should not need to know when to choose an experiment menu. This
work is tracked under TRACE-001 and is not yet a shipped default.

The development EFI builder now requires matching automatic-trace EFI/Lua
inputs and enables an observe-only loader-start checkpoint. Retrieve a returned
image or mounted hwtrace volume without changing it:

```sh
python3 tools/boottrace/stick.py normal TARGET --out FRESH_EVIDENCE_DIRECTORY
```

Keep that directory and the original returned bytes for the coding LLM. Supply
the exact model/board, firmware, boot path, image identity, last visible output
and the point where console access disappeared. Ask it to distinguish observed
facts from proposed experiments and preserve the working OS/recovery path.
A `loader-ready` record proves only that checkpoint: kernel, panic and installer
capture remain unfinished. See the linked default-tracing procedure for the
current native controls, full/readonly behavior and remaining persistence gaps.

The following reference retains the existing 1.5.x tools and separate-image
procedures for reproducible research and historical artifacts.

When a machine hangs or resets during kernel startup and nothing on screen
says why, use the hardware bring-up trace image. It is a separate image type
from the install/live ISO, because unattended cycling cannot coexist with
an interactive menu. The kernel (`debug.boottrace=1`) records each startup
step in UEFI NVRAM before the step runs. On every boot the loader:

- files the previous boot's trace on the stick
- clears the NVRAM
- boots the next queued experiment

[docs/boottrace.md](docs/boottrace.md) describes the record and the
tunables; this section is the procedure.

### Building the image

Build the image on the FreeBSD builder, from a kernel and loader built from
daemonarchy-src with boottrace, and the release ISO that kernel matches. The
ISO supplies `/rescue`, `pciconf`, `devinfo`, `timeout`, their libraries
and the modules:

```sh
sh build-hwtrace-image.sh -I daemonarchy-1.5.1-amd64.iso \
    -k obj/GENERIC/kernel -l loader_lua.efi -L src/stand/lua \
    -V 1.5.0-1 -o out
# -m "msdosfs ..." picks modules (default msdosfs); -s sets the DATRACE
# size in MiB (default 256); -S adds a serial console for VM tests;
# -x EXTRA.conf appends test knobs to loader.conf (never for a published
# image).
# -K KEYS puts public keys on the stick as KEYS/authorized_keys and -H makes
# its ssh host key at build time (a private image only): see the network
# hand-over in docs/boottrace.md. Without -K the image starts no network
# service.
```

The builder needs Python 3 (`python3` or `python3.12`): it runs
`tools/boottrace/stick.py write-map` on the assembled image, which fails the
build unless `STATE.TXT` and every `TRACES/` slot are contiguous.

The result is `out/daemonarchy-hwtrace-<version>-amd64.img` (about 390 MB)
and its `.sha256`. It has three GPT partitions:

- `EFISYS`: the loader.
- `HWTROOT`: a read-only UFS root holding the following:
  - `/boot`: the kernel, modules, Lua, the `/boot/d` presets and a
    `loader.conf` whose only behaviour is the cycle
  - a rescue root whose `/etc/rc` runs when a boot reaches init. It saves
    `dmesg`, allowlisted scalar `sysctl` values, `kenv`, `kldstat`,
    `pciconf -lvbc`, `devinfo -vr` and USB descriptors to `DATRACE/DUMPS/<experiment>/`
    on a synchronous FAT mount and reboots. Each probe has a time limit;
    `capture.log` records starts and exit statuses; ACPI discovery is performed
    by the optional loader capture described in `docs/boottrace.md`.
    The queue line `hwtrace.shell=YES` gives a shell instead.
- `DATRACE`: a FAT32 volume with `DATRACE.TAG`, `STATE.TXT`, `QUEUE/`,
  `TRACES/`, `DUMPS/` and `SLOTS.MAP`.

`SLOTS.MAP` is the block map: the byte offset and size, inside the
partition, of `STATE.TXT` and each preallocated `TRACES/NNNN.TXT` slot,
with the partition's start and length and a checksum. The loader rewrites
those sectors through `EFI_BLOCK_IO`, flushes the partition and the disk,
and reads them back through the disk's BlockIo. It does not write through
the firmware FAT driver. On the MSI Raider, FAT-driver writes were
acknowledged, read back from the driver's cache, and never reached the
stick. `stick.py check-map IMAGE` verifies a map, and `write-map` rewrites
it. A stick without a map, such as one made by an older builder, falls back
to the FAT driver.

`tools/boottrace/qemu-stick-test.py IMAGE --vars VARS.fd --log LOG` boots an
image under QEMU/OVMF. It resets silent boots the way laptop firmware does.
On an arm64 host, add `--cpu Westmere` (x86 TCG). For the failure tests,
build an image with `-S -x knobs.conf`, where `knobs.conf` holds
`boottrace_test_drop="fat"`, `"raw"` or `"all"`. The loader then
acknowledges those writes without making them, which imitates the MSI.

### Experiments

Write a queue on any host with mtools; Linux can also mount `DATRACE`
directly:

```sh
tools/boottrace/stick.py queue IMAGE-or-DEVICE-or-MOUNT experiments.txt
tools/boottrace/stick.py status TARGET
tools/boottrace/stick.py traces TARGET --out traces/   # readable text
```

An experiments file is a list of `[name]` blocks. Each line is
`name=value`, `unset name` or `read-conf /boot/d/N`, applied after the image
defaults (trace on, `boot -v`, panic reset after 15 s):

```ini
[legacy-off]
read-conf /boot/d/1

[legacy-off-one-cpu]
read-conf /boot/d/1
kern.smp.disabled=1

[zoom-from-clocks]
debug.boottrace.from_sub=0x4800000
```

`queue` replaces the queue and keeps filed traces; `--reset-traces` deletes
them. It also starts a new queue generation (`epoch=` in `STATE.TXT`).
`stick.py` rewrites `STATE.TXT` and the slots in place: raw through the map
on an image or device, and without truncation on a mounted volume. Their
sectors therefore never move.

### At the machine

1. Once, in the firmware setup, put USB first in the boot order. Secure Boot
   stays off.
2. Attach the stick and power on. Every boot and every firmware reset runs
   the next experiment. The loader shows **HARDWARE TRACE: STOPPED** when a
   boot reached init or the queue is empty. It also stops with **STICK
   WRITES ARE NOT PERSISTING** when its NVRAM self-report (`DBTLoader`)
   says the previous cycle wrote `STATE.TXT` but the stick does not hold
   it. In that case the last kernel trace stays in NVRAM; read it with
   `boottrace show` or the Windows reader. It also stops when the same
   experiment would be staged a third time in a row
   (`boottrace_max_repeat`, default 2). A new `stick.py queue` or
   `boottrace clear` starts over.
3. Detach the stick and bring it back. Read `TRACES/` with `stick.py traces`
   and `DUMPS/`, write the next queue and reattach.

### Zooming in and the NVRAM budget

Variable stores append a copy on every write and rarely reclaim at runtime.
A laptop store may have only tens of KiB free; the MSI Raider has 55 KiB.
Each boot therefore spends the free space `QueryVariableInfo` reports, less
a reserve. The reserve is a quarter of the maximum variable size, kept
between 8 and 16 KiB; `debug.boottrace.reserve_kb` overrides it.

Each step writes a 64-byte breadcrumb, which costs about 140 bytes of store,
so roughly 250 to 300 fit in 40 KiB. Breadcrumbs go to a ring of 16
variables, `DBTStep00` to `DBTStep15` (`debug.boottrace.ring`), overwritten
in place. The newest 16 steps before a hang are therefore always on NVRAM,
and the live footprint stays about 2 KiB. Every 32 breadcrumbs, the kernel
reads `QueryVariableInfo` again. When the firmware has freed space at
runtime, the budget grows. When the budget runs low, it persists every 2nd,
then every 4th step, and so on, instead of stopping. The last breadcrumb
therefore lands near the hang, and the trace says so (flag `strided`). The
full record with the message tail is written only at checkpoints, panic and
completion. By default, steps
before `debug.boottrace.from_sub` (`SI_SUB_CONFIGURE`) are persisted only at
subsystem boundaries; after it, every SYSINIT, attach, config hook and each
device's first probe is. To zoom in:

- Move `from_sub` later, or set `debug.boottrace.from=N` to persist every
  step from step N.
- If a trace says the budget ran out, its last step is the place to start
  the next experiment from.
- Each trace records the store figures, so you can see whether the firmware
  reclaims between boots. `boottrace_compact="YES"` in `loader.conf` makes
  the loader try to force a reclaim; it is off by default because on OVMF
  it can leave less space.

### Windows fallback

If the machine falls through to Windows, run this from an elevated
PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File tools\windows\read-boottrace.ps1
```

It reads `DaemonarchyBootTrace`, the breadcrumb ring (`DBTStep00`..; older
kernels wrote a single `DBTStep`) and the loader's `DBTLoader`
self-report. It writes a text and a raw copy to the desktop; `-Clear`
deletes the trace variables.

## Releasing

### Build a release from your own checkout

Use the [1.5.0 mastering notes](docs/mastering-1.5.0.md) as the worked example
and the exact input/asset identities in [its release record](verification/release-1.5.0.json)
to reproduce it. For a new release, review one product commit and exact source,
ports, desktop, compatibility and framework selections. On native FreeBSD
workers, build the matching world/kernel/sets and jail, application and checkout
feeds, any needed closure shards, signed boot products and installer images.
Record the selections and native/VM/hardware results before publication.

`scripts/master-release.sh` runs the resumable native build, verification and
QA steps. Supply a private config with the reviewed `MAIN_COMMIT`, `RELEASE`,
`SOURCE_REVISION`, `PORTS_REVISION`, `JAIL`, `PTREE`, feed tags, checkout
catalogue, public Secure Boot bundle and output paths. Its defaults are
historical examples. Inspect the config and dry-run before dispatch:

```sh
./scripts/master-release.sh --config /path/to/reviewed-master.conf --dry-run all
./scripts/master-release.sh --config /path/to/reviewed-master.conf preflight packages
./scripts/master-release.sh --config /path/to/reviewed-master.conf secureboot feed
./scripts/master-release.sh --config /path/to/reviewed-master.conf resolve catalogue iso verify hwtrace qa
```

The `secureboot` and `feed` steps need the protected signing workflow in
[the mastering notes](docs/mastering-1.5.0.md#key-windows-signing-without-a-key-on-the-builder).
`sticks` writes explicitly selected USB devices and is separate from `all`.
Before publication, fill the release record and notes, run
`python3 tests/docs-release-sync.py -v` and verify staged assets with
`scripts/verify-release-assets.py` as shown in
[Filling the records](docs/mastering-1.5.0.md#filling-the-records). Publish
only after exact artifact QA; published tags and bytes are immutable.

### One signing session per release

Sign once. Freeze every signed input (the boot tree files `secureboot/*` and `brand-daemonarchy.lua`, the kernel and loader, the
kernel modules and firmware in the amd64 set, the release label, the feed package sets and the extension bundles), finish QA on the
unsigned artifacts, then run the key windows in one sitting. A change to a frozen input after signing needs another window.
The windows and their safeguards are in [Key windows](docs/mastering-1.5.0.md#key-windows-signing-without-a-key-on-the-builder); the
rule is [there](docs/mastering-1.5.0.md#one-signing-session-per-release-the-rule); the reasons and options are in
[SIGN-001](docs/roadmap/release-1.5.0.md#sign-001-one-signing-session-per-release). Agents never hold or move key material.

### Maintaining the release history

Update [CHANGELOG.md](CHANGELOG.md) with every release change. Keep the current
release under an explicit unreleased heading until publication; backfill missed
changes from the actual commit/tag and GitHub release history. Record concrete
behavior, source/ports or ABI migrations, validation and material limitations.
Distinguish published releases, prereleases, drafts and supporting feeds; an
approval or release commit does not establish publication. Use UTC publication
dates and link the corresponding qualification record so both humans and agents
can follow the evidence. Final publication updates the changelog, download links
and current-status documentation together.

### Packages

A compatible application fix can reach existing installations through their online repository without a new image. The unversioned publication command below is only for packages compatible with that feed's retained base. From 1.1.1 on, use the versioned rebuilt-dependency procedure below and leave the unversioned feed unchanged. After rebuilding the compatible packages (step 4 of the build host setup), run this from a workstation with `gh`:

```
./pkg-repo.sh publish
```

It copies `origins.sh` and itself to the build host (`BUILD_HOST`, default `freebsd.local`), and collects and signs the `OMARCHY_ORIGINS` packages there. It then replaces the assets of the `packages-16-amd64` release, uploading the packages first and the catalogue last. That release is never marked latest, so the latest release stays the ISO.

The signing key is `/usr/local/etc/daemonarchy/pkg-repo.key` on the build host. Make it once with `pkg-repo.sh keygen`, and commit the public key it prints as `overlay/usr/local/share/daemonarchy-installer/daemonarchy.pub`. Keep a copy of the private key somewhere safe. If it is lost, a new key has to be put on every installed system by hand.

The 1.3.1 release used a separate versioned feed and a new key because the old
private key was unavailable on the build host. Follow
[the rotation plan](docs/package-repository-key-rotation-1.3.1.md) before
publishing or changing an installed repository configuration.

### Images

Daemonarchy releases use [semantic versioning](https://semver.org), numbered on their own rather than after Omarchy's or FreeBSD's releases (the notes say which of each a release carries). The number is the daemonarchy-desktop tag that `x11-wm/daemonarchy` fetches (its `DISTVERSION`):

- **Patch** (1.0.1): fixes only.
- **Minor** (1.1.0): new features that leave existing installs working as they were.
- **Major** (2.0.0): changes an existing install cannot simply upgrade into, such as a new FreeBSD branch or a disk layout the installer no longer makes.

Package-only fixes between images bump `PORTREVISION` instead and ship through the package repository.

For a candidate, publish the signed application repository under a versioned
tag (for example, `packages-16-amd64-1.1.0-candidate`) and verify it with a native
client. Keep the default stable package feed unchanged until stable qualification
is complete. Publish the installer as a prerelease with `--latest=false`, and
retain the open hardware gates in its notes.

Build a candidate image with `PACKAGE_REPOSITORY_TAG` set to its versioned
application-feed tag (for example, `packages-16-amd64-1.1.1`). The image
records that selection and installed systems retain it as their signed
Daemonarchy feed. Omitting the variable selects the stable feed. Set
`EXPECTED_PACKAGE_REPOSITORY_TAG` to the same tag when running `test-qemu.sh`;
the installed-system check asserts the exact feed URL.

When the selected ports tip is ahead of the official binary collection, the
candidate feed must include rebuilt ordinary dependencies as well as the
Daemonarchy ports. Collect a union of the successful `.poudriere.ports.built`
records from this candidate's build/test attempts into `BUILT_PACKAGES_FILE`.
Use `pkg-repo.sh collect` on the builder with `BUILT_PACKAGES_FILE` and the
versioned `TAG` to stage public payloads without a signing key. Transfer those
payloads into an `All` directory on the protected signing host. There, use
`PACKAGES_DIR` for the staged repository, `BUILT_PACKAGES_FILE` for that list,
and the same versioned `TAG` when running `pkg-repo.sh build`. Kernel-bound packages remain on the matching ISO.
The installer uses the signed candidate feed to resolve these dependencies,
then records them under the normal Daemonarchy repository for later upgrades.
The rebuilt-dependency option refuses the unversioned stable feed.

`sudo bash tests/pkg-repo-dependencies.sh` exercises real signed repositories,
dependency resolution and subsequent upgrades in disposable pkg roots.

For an existing test installation, select the versioned candidate URL in
`/usr/local/etc/pkg/repos/Daemonarchy.conf`, then run
`sudo bash scripts/adopt-candidate-packages.sh` from this checkout. This
reinstalls already-installed feed packages from Daemonarchy, including rebuilt
dependencies that `pkg` can otherwise retain from their previous repository.
Before changing any package identities, the helper compares the actual kernel
and userland OSVERSION values with the candidate catalogue's
`FreeBSD_version` requirements. Missing or malformed requirements on native
packages are refused; architecture-independent packages may omit them. A newer
feed requires a coordinated base, kernel and driver upgrade first. This check
also applies when pkg's automatic yes or OS-version overrides are enabled:
`pkg install -y` alone accepts newer-OS packages and does not provide this guard.
After that check it assigns those public packages to Daemonarchy, then uses normal
dependency resolution so newly required official packages remain available.
Unrelated build dependencies and private-repository overrides are preserved.
The feed choice takes effect before installation; after a failed transaction,
resolve the package error and rerun the helper. Normal `pkg upgrade` follows
that one-time transition; changing the FreeBSD base/kernel remains a separate
coordinated operation.


1. Tag daemonarchy-desktop `v<version>`, set `DISTVERSION` in `x11-wm/daemonarchy` to it and run `make makesum`, then build the packages and the image as above, publish the packages, and run a test.

   The release version lives in one place, the `VERSION` file. Change it with
   `python3 scripts/version.py set X.Y.Z` before building (`show` and `show
   --json` read it, `check` verifies the copy in `literate.project.json`).
   `build-iso.sh` takes the installer screen's version line and the default
   image name from it, not from the `daemonarchy` package, which is reused
   across releases. Bump it in the same change that starts a release cycle.

   **Closure feeds (mandatory from 1.4.1).** The installer must not depend on
   pkg.FreeBSD.org's moving `latest` (it dropped `tigervnc-viewer` one day after
   1.4.0 and every fresh install failed). Each release hosts the whole installer
   closure, upstream packages included, as signed, versioned, non-latest GitHub
   release feeds per architecture, and the image prefers them. Before the ISO is
   built and tested:
   1. Resolve the closure: `scripts/package-mirror-plan.py --json --upstream FreeBSD`
      over the ISO's package catalogue, our application feed and
      `pkg.FreeBSD.org`, with the fixed roots plus every GPU, Wi-Fi and CUDA
      selection root. It must report `unsatisfied: []`.
   2. Fetch the hosted archives (`parallel-fetch`, about 4 connections to
      pkg.FreeBSD.org) and stage them with `scripts/package-feed-stage.py stage`,
      signed on the build host with the release's pkg repository key (the key
      never leaves that host). It copies each archive under a GitHub-safe name,
      builds the signed catalogue and requires its checksums to equal upstream's;
      `verify` re-checks the shard. Shards stay under 900 packages (GitHub allows
      1000 assets, 2 GiB each); every asset is already compressed (zstd packages and
      the pkg catalogue); nothing uncompressed is uploaded.
   3. `package-feed-stage.py publish-plan` writes the exact `gh` commands. The
      operator approves it; every tag is new (`packages-16-<arch>-<version>-upstream`
      or `-upstream-N`), `--latest=false`, never replaced in place, and packages
      upload before the catalogue that names them. Verify with an independent
      re-download hash check.
   4. Record every feed's per-asset size and SHA-256 in the release-inputs record
      (`closure_feeds`). `scripts/verify-release-assets.py --closure-assets DIR`
      (and `--published`) refuses a 1.4.1-or-later record without them, any raw
      payload or private key material, and a published feed that is draft, the
      latest release, or differs in asset names, sizes or digests.
   5. Build the ISO with `PACKAGE_MIRROR_URLS` naming the shards and
      `REQUIRE_PACKAGE_MIRROR=yes`: `build-iso.sh` then refuses a feed that is
      missing, not answering, unsigned, or that does not resolve the installer
      roots with pkg.FreeBSD.org disabled (`scripts/check-closure-feed.sh`).
   6. **Closure refresh.** `scripts/package-mirror-plan.py --fail-on-unsatisfied`
      is a release gate and runs daily (`upstream-drift.yml`). When upstream moves
      (a package disappears or changes soname, as `tigervnc-viewer`/`fltk` did),
      build the missing package with our ports, add its origin to `origins.sh`, and
      stage a new snapshot as the next `-upstream` tag; do not edit a published one.

2. Finish required review/checks, merge and synchronize the installer source,
   then tag the exact reviewed commit. Publish a normal stable GitHub release
   `daemonarchy-<version>`, marked latest. Standard public assets are the ISO,
   its `.sha256`, `daemonarchy-<version>-boot.txz`, its detached `.sig`, and
   the matching public Secure Boot certificate in PEM and DER form. From 1.4.0
   the ISO is published xz-compressed as `daemonarchy-<version>-<arch>.iso.xz`,
   and the published `.iso.xz.sha256` covers the compressed bytes users
   download. `build-iso.sh` writes both after checking that the `.xz`
   decompresses to the exact built image. Do not upload the raw `.iso` or its
   `.iso.sha256`; they stay local for VM QA and native evidence, which binds
   the uncompressed image digest. Releases through 1.3.1 keep their raw ISO
   assets unchanged. The 1.3.1
   candidate rotates that certificate because the previous private signing key
   is unavailable; do not reuse the 1.1 certificate names for a different key.
   The published 1.5.0 release carries amd64 and aarch64 installers, amd64 and
   aarch64 hardware trace images, their four checksums, the amd64 signed boot
   bundle and signature, and the public certificate in PEM and DER form. Use
   [the exact release record](verification/release-1.5.0.json) for its twelve
   asset names and hashes. A new release needs its own reviewed record and
   publication plan; do not reuse the 1.5.0 tag or asset names.

   Verify the exact uploaded asset names, sizes and SHA-256 digests. Keep
   release-specific application and checkout feeds non-latest. Operator-approved
   physical qualification deferrals must remain explicit limitations in the
   release notes; they never become passing results. Leave the unversioned
   stable application feed unchanged.

   **The extension feed** (from 1.4.1; [extension-feed.md](docs/extension-feed.md)).
   Installer extensions, the arcade games first, are not on the ISO: they are
   downloaded when the user chooses them. For each architecture, stage a release
   `extensions-<os>-<arch>-<version>` (for example `extensions-16-amd64-1.4.1`)
   with `python3 scripts/extension-bundle.py stage extensions/games/* --out DIR
   --feed <tag> --arch <arch> --key <signing key> --pubkey <pinned public key>`.
   Sign with the private key whose public half the image pins as
   `daemonarchy.pub` (the package repository key; staging with a throwaway key and
   re-signing with `extension-bundle.py sign` changes only the `.sig` files), then
   `extension-bundle.py verify DIR --pubkey <pinned public key> --feed <tag>`.
   Everything published is compressed (`.tar.xz` bundles and the `.json.xz` index)
   or a signature; record the table `extension-bundle.py table DIR` prints
   (names, compressed and uncompressed sizes, SHA-256). Create it as a
   **non-latest** release with a new tag, never an existing release or the
   latest, and upload exactly those assets. Install from the exact image against
   the published feed (download, verify, run), and once with the network blocked
   to confirm the offline message. Rebuild and re-publish the feed whenever an
   extension or the SDK API it needs changes.

   Before upload, run `python3 scripts/verify-release-assets.py --record
   verification/release-1.3.1.json --assets /path/to/staged-assets` on the six
   staged public assets. It checks exact sizes and digests, the ISO checksum
   file, matching PEM/DER certificate, the detached boot-bundle signature,
   its internal files, and its source/OSVERSION identity. Native ISO runtime,
   physical hardware, signed feed and post-upload checks remain separate gates.
   After publication, rerun the same command with `--published` to compare the
   GitHub stable latest release, annotated tag target and all six uploaded
   asset sizes and SHA-256 digests with the exact local record.

3. Once `--published` passes, bring the release media and every document into
   sync in the same release cycle; the release is not finished until this lands
   on `main`. Never point any document at a draft, prerelease or unpublished
   release. (After 1.3.1 shipped, the README and getting-started guide kept
   advertising 1.1.1 until this step was enforced.)

   1. **Update the source of truth first.** Run
      `python3 scripts/release-current.py update daemonarchy-<version>
      --osversion <N> --application-feed <tag> --checkout-feed <tag>`. It reads
      the published GitHub release, not local build outputs, and rewrites
      [`release/current.json`](release/current.json): version, tag, publication
      time, every published image type (the installer ISO for each
      architecture, and any other image product such as the hardware-trace
      bring-up image) and the exact names, sizes and SHA-256 digests of all
      public assets. The previous release moves to `previous_releases`, so its
      image name, size and checksum become stale wherever a current-state
      document still carries them. `python3 scripts/release-current.py
      check-published` compares the file with GitHub's latest release at any time.
   2. **Run the guard:** `python3 tests/docs-release-sync.py -v`. It lists every
      current-state document that still names an older release as current, an
      older image name, checksum or size, or an unreleased version as available.
      Fix each one; do not weaken the guard or mark a current-state document
      historical to silence it. CI runs it on every pull request that touches
      documentation, release records or this procedure.
   3. **Work through the checklist.** The guard catches identifiers, not
      meaning, so also review:
      - **Download section and current-release section of `README.md`:**
        release name and link, the image and checksum links for *all published
        image types*, byte sizes and SHA-256 values from the verified published
        release, the `dd` (or `xz -dc | dd`) example, and the release notes with
        their limits. Turn the previous release's text into history.
      - **Release notes** (`docs/release-<version>.md`): published state, final
        asset identities and limits, linked from `README.md` and `docs/README.md`.
      - **Every other current-state document**, as listed by
        `python3 tests/docs-release-sync.py --list`: `HACKING.md` (this file's
        current-release header and examples), `PROJECT.md`, `ROADMAP.md`,
        `docs/getting-started.md`, `docs/README.md`, `docs/hardware-quirks.md`,
        `docs/remote-agent-debug.md`, `docs/secure-boot.md`, the image guides
        for each published image type, and `secureboot/` READMEs. Hardware
        support, install procedure and feature descriptions must match what the
        release actually ships; a feature still in development is described as
        upcoming with a link to its roadmap entry.
      - **The image's own shipped documentation and data** under `overlay/`
        (installer help text, the default checkout catalogue
        `overlay/usr/local/share/daemonarchy-installer/checkouts.json`, and any
        version-naming text) for every published image type.
      - **Checksums and image names** for all published image types, including
        the separate hardware-trace bring-up image once it is published.
      - **Historical records** (`docs/testing-*.md`, earlier release notes,
        `CHANGELOG.md` entries, roadmap ledgers) keep their versions; add a
        `<!-- release-sync: history -->` passage only for genuine history inside
        a current-state document.
4. If the release replaces one with a serious bug, say so at the top of the old release's notes.

## Pitfalls met so far

- **Swapped-out guests panic.** A bhyve guest paged out by a host short of memory stalls long enough for its kernel's deadlock detector to panic mid-install. Wire the guest's memory, and don't overcommit the host.
- **QEMU's AVX2 emulation faults in ZFS.** With `-cpu max` under emulation, ZFS's AVX2 SHA-256 code page-faulted; use a CPU model without AVX (`-cpu Westmere`).
- **SDDM matches sessions by full path.** Omarchy's login theme has no user list; it signs in as SDDM's last user and session from `/var/lib/sddm/state.conf`. FreeBSD's SDDM needs the session as `/usr/local/share/wayland-sessions/omarchy.desktop`; a bare name falls back to plain Hyprland.
- **Sound needs the `audio` group** on FreeBSD 16.
- **pkg pads its install counter** (`[ 119/1184]`); anything parsing it must allow the space.
- **Boot code goes stale after ZFS upgrades.** A pool that gains new features (after `zpool upgrade`) needs current boot code, or the machine stops at `boot:` with "unsupported feature". Inspect `gpart show` before updating matching boot files: the 1.1 whole-disk layout uses **p4** for BIOS `freebsd-boot`, while **p1 is the EFI filesystem**. Update only the verified boot partition or project EFI loader; shared-disk installs preserve other operating-system loaders. Do not apply an old p1 BIOS recipe to this layout.
- **The snapshot directory moves.** `download.freebsd.org/snapshots/.../16.0-CURRENT` always holds the newest snapshot, but the image's sets must be the ones the jail was made from, or the kernel modules on the image will not match its kernel. The authoring cache retains those verified inputs. Select a separate `SET_CACHE_DIR` when moving snapshots, then create the matching jail and rebuild its modules. The image build refuses a different jail version or a source catalogue that does not match its kernel.
- **pkg -r resolves accounts on the running system.** Installing into `$TARGET` from the live system gave every file owned by an account a package creates (`messagebus`, `polkitd`, `cups`, `colord`) to `root:wheel`, which broke D-Bus service activation and with it polkit prompts. `fix-ownership` re-applies each package's recorded owners, groups and modes inside the target after the install.
- **pkg -r runs triggers on the running system.** The packages' triggers (`/usr/local/share/pkg/triggers`) call tools such as `glib-compile-schemas` by absolute path, which the live installer does not have, so an install was left without compiled GSettings schemas and GTK applications such as Files aborted at start. `rebuild-caches` runs them inside the target.
- **The session's PATH is GNU first.** Omarchy's commands put GNU coreutils (`libexec/omarchy/gnubin`) ahead of FreeBSD's, so a FreeBSD-only flag such as `tail -r` fails when the command runs from the desktop even though it works in a plain shell. Test Daemonarchy's commands from a desktop terminal, or avoid the flags.
- **The package mirrors disagree.** poudriere's default `pkg+http://pkg.FreeBSD.org` hands each run a random mirror, and a mirror partway through a sync gives it a partial catalogue: one run fetched 56 packages where the next fetched 1,178, and built the rest from source. Pin `PACKAGE_FETCH_URL` to `http://pkg.FreeBSD.org/${ABI}` (step 3). The mirrors can also be slow from a given host (100 to 400 KB/s here); a faster machine can download the packages and copy them into the repository's `.pkg-cache`.
- **The official set's dependency versions lag.** pkg.FreeBSD.org builds incrementally, so some of its packages record older versions of their dependencies than the set now holds (chromium recorded `dbus-glib-0.114` while the set had 0.116). poudriere then refuses or deletes them and builds them, chromium and LibreOffice included, which takes most of a day. At a matching official baseline those dependencies can be fetched. A newer integration such as 1.1.1 instead needs the incompatible dependencies rebuilt and retained in its separate versioned feed; don't silently substitute older packages or overwrite the stable feed.
- **Quoting through ssh.** Don't pass code containing apostrophes inside `ssh host '...'`: a stray quote ends the remote command early and runs the rest locally. Write the file locally and copy it with scp instead.

## Optional installed ports and source trees

See [the sizing report](docs/optional-source-sizing.md) for `/usr/ports` and
`/usr/src` archive locations, measured sizes, and installation-space allowances.
These development installer options require archives pinned to the release
ports integration and the installed FreeBSD snapshot.

### Secure Boot development

Secure Boot development is documented separately in
[`secureboot/README.md`](secureboot/README.md), with the
[manual-enrollment contract](docs/secure-boot.md) and
[native development evidence](docs/testing-1.1-secureboot.md). Stable 1.0.1 and preview.1 do not implement that production path; the 1.1
candidate integrates it using public signed artifacts. Its private signing key must stay
off build payloads and public images.

The integration build accepts **public artifacts only**:

```sh
sudo env SECUREBOOT_BUNDLE=/path/to/signed-boot.txz \
  SECUREBOOT_SIGNATURE=/path/to/signed-boot.txz.sig \
  SECUREBOOT_CERTIFICATE=/path/to/public-certificate.pem \
  ./build-iso.sh
```

Prepare and sign those artifacts using the separate boot-tree workflow in
`secureboot/README.md`. The signing key is not an input to `build-iso.sh` and
must stay on its protected signing host. Keep disposable development keys and
images private; only the production public certificate belongs in a release.
The post-build hook validates the archive, stock kernel and actual live boot
files before ISO creation. The installer repeats validation before partition
writes, installs the profile after the base/rescue setup, and checks the target
again after package installation. It preserves other EFI loaders and never
changes firmware PK, KEK, db or dbx.

With the payload present, firmware-enforced UEFI selects the verified kernel;
UEFI with enforcement off and BIOS use the stock kernel. The signed EFI loader
also follows the installed pool's active boot environment through its numeric
GUID. Builds without this payload retain the older loader/explicit dataset
selection and cannot qualify Secure Boot. Packages owning boot modules are
locked to the signed inventory; ordinary applications remain upgradeable.

For an installed verified profile, same-snapshot maintenance is explicit:

```sh
sudo daemonarchy-secureboot stage update.txz --signature update.txz.sig \
  --certificate /usr/local/share/daemonarchy-secureboot/certificate.pem \
  --environment update-1.1-test
sudo daemonarchy-secureboot activate update.txz --signature update.txz.sig \
  --certificate /usr/local/share/daemonarchy-secureboot/certificate.pem \
  --environment update-1.1-test
```

Staging never activates or reboots. Activation rechecks the candidate, then
selects it for the next manual reboot; the previous environment is retained.
A failed stage stays unactivated and is retained for diagnosis. Changing a
driver needs the matching signed inventory and native package in that candidate;
do not overwrite pkg-owned driver files or unlock them in the running profile.
Base/ABI transitions, certificate rotation and an EFI loader-protocol change
need a separately qualified migration. The [1.1 record](docs/testing-1.1-upgrade.md)
contains native same-snapshot maintenance evidence; the [1.1.1 record](docs/testing-1.1.1.md)
tracks the new snapshot separately. Preview.13 lacks these integration commands.

For enforced QEMU installation tests, use separate fresh work directories and
persistent variables cloned from an already enrolled disposable template:

```sh
BOOT_MODE=uefi UEFI_SECUREBOOT=true \
  UEFI_CODE=/path/to/OVMF_CODE_4M.secboot.fd \
  UEFI_VARS_TEMPLATE=/path/to/enrolled-test-vars.fd \
  WORK=/path/to/fresh-test SSH_PORT=22461 sh test-qemu.sh private-test.iso
```

The harness keeps one private variable store across installation and reboot,
then checks real firmware state, verified kernel selection and locked policy.
Add `ENCRYPT_INSTALLATION=true` for GELI. For actual graphical checks, set
`VIRGL_RENDER_NODE=/dev/dri/renderD128`, an unused loopback `VNC_LISTEN`, and
`POST_INSTALL_CHECK="$PWD/tests/qemu-desktop.py"` on a qualified Linux/VirGL
worker; the callback performs password login (or encrypted-install autologin),
keyboard and pointer input, retaining screenshots and a JSON receipt. Services
running over SSH alone do not qualify graphics. `MEM=8G` can give that guest
more memory. Native firmware/graphics test results must still be recorded.

### Building live checkout packages

The optional trees are **depth-1 shallow Git checkouts**, not full repository
history. They include `.git`, the release revision and a configured HTTPS remote.
Users can fetch changes, deepen history and commit. Package files own only seed
archives in `/usr/local/share/daemonarchy/checkouts`; the working trees in
`/usr/ports` and `/usr/src` are independent, so package removal cannot delete work.

On the FreeBSD build worker, run `scripts/build-checkout-packages.py` for each
release input. Use the image's integrated ports revision and the source revision
printed in the selected kernel's build identity:

```sh
python3 scripts/build-checkout-packages.py --kind ports \
  --repo /usr/local/poudriere/ports/omarchyiso --revision <ports-commit> \
  --branch main --remote https://github.com/jordanhubbard/daemonarchy-ports.git \
  --out /path/to/checkout-repo
python3 scripts/build-checkout-packages.py --kind src \
  --repo /usr/src --revision <kernel-source-commit> \
  --branch daemonarchy --remote https://github.com/jordanhubbard/daemonarchy-src.git \
  --out /path/to/checkout-repo
python3 scripts/make-checkout-catalog.py /path/to/checkout-repo \
  --url https://github.com/jordanhubbard/daemonarchy/releases/download/<checkout-tag> \
  --ports-tracking-branch main \
  > /path/to/checkout-repo/checkouts.json
sudo pkg repo /path/to/checkout-repo /usr/local/etc/daemonarchy/pkg-repo.key
```

`--depth` defaults to 1. The 1.5.0 checkout feeds track ports `main` and
source `daemonarchy` at the commits in their catalogues. The earlier 1.1.1 tracked
freebsd-ports `daemonarchy-1.1.1` and FreeBSD `main`, and older 1.1 images retain
their pinned `daemonarchy-1.1-package-baseline` catalogue and feed. Default fetches are restricted to one branch. Payloads are split into 512 MiB parts before packaging,
keeping each asset below 2 GiB. Publish the signed repository at a dedicated,
release-specific tag, packages first and catalogues last. Retain that tag for
older installations. Pass `CHECKOUT_CATALOG=/path/to/checkout-repo/checkouts.json`
to `build-iso.sh`; it rejects sources that do not match the selected kernel.
The checkout packages are downloaded when selected and do not enlarge the ISO.

The installer offers each tree separately. Unattended installs default both off;
set `install_ports=true` and/or `install_src=true` to enable them. Selections
increase the required disk/partition size by the measured peak-space allowance.
The checkout is owned by the new user. Later, install either tree with:

```sh
sudo daemonarchy-checkouts ports "$USER"
sudo daemonarchy-checkouts src "$USER"
```

The command refuses nonempty destinations and verifies payload checksums. It
also refuses to install source from a catalogue for a different kernel snapshot.
Seed packages and pkg's download cache can be removed after successful creation;
the command lists the seed package names. Build dependencies, distfiles and
compiler outputs still need additional disk space.

Run `sudo bash tests/checkout-packages.sh` on FreeBSD for the native package
round trip, shallow/deepen/commit checks, edit preservation and corruption
rejection. `bash tests/checkout-options.sh` checks selection and capacity policy.
