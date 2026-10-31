# The graphical package manager (design)

Status: **in progress.** The toolkit-free layers (repositories, catalogue, plan, shared
engine, text commands) are in `apps/daemonarchy-pkg/` with tests in `tests/gui-package-manager.py`.
The transaction helper (`daemonarchy-pkg-helper`) and the window's progress model are in too.
The window, the menu entries and the package are not done, and nothing is shipped. It is the plan for the
GUI-001 queue item ([acceptance](roadmap/active-work.md#gui-001-deliver-a-colorful-fast-graphical-package-manager)).
Until it ships, the graphical package manager is OctoPkg.

## What the queue item asks for

Install, update and remove with the same useful visual progress and parallel execution
the installer has; share the transaction engine and progress semantics rather than
build a competing planner; evaluate the existing manager first; contribute a port only
if a new application is needed. Evidence: real native UI and input, a plan identity
shared with the engine, accurate progress, failure and retry, packaging tests.

## Evaluation of OctoPkg 0.4.1 (the current manager)

| Need | OctoPkg | Consequence |
| --- | --- | --- |
| Plan before acting | shows pkg's own prompt text | no plan object, no identity, nothing to share |
| Parallel download | none; one `pkg` process | cannot show or use `parallel-fetch` |
| Progress | parses pkg's terminal output | no byte totals, no per-archive state |
| Signed feeds | whatever pkg does; not shown | the user cannot see which repository or key supplied a package |
| Extension points | C++/Qt, no plugin or event hook | adding the above is a fork we would carry |

Conclusion: extending OctoPkg means carrying a Qt fork whose engine side we would still
have to replace. The engine is the part worth sharing, and it already exists in Python
here, so the new application is small and the port is ours. OctoPkg stays installed as
the fallback until the new application has real-desktop evidence.

## Architecture

`daemonarchy-pkg`: Python with the GTK 4 bindings the desktop already installs
(`pygobject`, `gtk4`; no new runtime dependency). Four layers, the first three
toolkit-free so they are tested headless on any host:

1. **Catalogue** reads the repositories' sqlite databases read-only (the way
   `parallel-fetch` reads exact sizes), with one in-memory index. Search is incremental,
   by name, comment and category; the UI never calls `pkg search` per keystroke.
2. **Plan** asks pkg for a dry run (`pkg install|upgrade|delete -n`) and turns it into an
   object: packages to install, upgrade, remove, reinstall; exact download and
   installed bytes; the repository each archive comes from; and an identity, the
   SHA-256 of the canonical plan. This is `parallel-fetch --plan-only` and its
   `@@plan` line (`daemonarchy/install-plan@1`), reused, not reimplemented.
3. **Transaction** runs a plan by identity. A small root helper (started through
   `sudo -A`, so the existing askpass prompt appears) recomputes the plan, refuses to
   run if its identity differs from the one the user approved, runs `parallel-fetch`
   for acquisition and then `pkg` for the install or remove. It emits the installer's
   events (`@@plan`, `@@fetch`, per-package `[n/N]`), which the screen consumes through
   `progress-model` (`Progress`, so counts and bytes mean exactly what they mean in the
   installer: distinct packages clamped to the plan, bytes banked across pkg runs, rates
   measured, estimates labelled). Failure and retry are states of the transaction:
   a failed archive is retried singly by the pool; a failed step offers Retry, which
   re-plans and shows the new identity if anything changed.
4. **Window** (GTK 4): sidebar of views (Browse, Installed, Updates, Queue, Repositories),
   a results list, a detail pane, and a transaction sheet showing the plan, then the
   progress. Colour comes from the SDK palette (`daemonarchy_visual.palette`) turned into
   one CSS file, so the colours match the installer and the terminal tools; the SDK has
   no GUI toolkit, so the SDK's role here is palette, formatting (`format_hms`, sizes)
   and the shared progress model, not drawing. No private rendering path exists in the SDK
   to bypass. Motion follows reduced-motion (`DAEMONARCHY_REDUCED_MOTION=1` or GTK's
   `gtk-enable-animations`): the same information, no animation.

Without a display `daemonarchy-pkg` falls back to `--plan` and `--status` text output,
which is also what the tests drive.

## Signed-feed awareness

Each repository shows its name, URL, enabled state, `signature_type`, and the fingerprint
of the pinned public key, read from the `.conf` files the same way pkg does. A repository
without a signature is marked and its packages carry a warning in the plan; installing
from it needs an explicit confirmation naming the repository. The Daemonarchy closure
feeds (`packages-16-<arch>-…-upstream`) and pkg.FreeBSD.org are listed in the order pkg
prefers them, and the plan says which one supplies each archive.

## Fast

Numbers to meet, measured on the installed desktop, recorded when measured:
first window under one second from launch with a warm catalogue; search results within
one frame of a keystroke over the full catalogue (about 35,000 packages); no blocking
call on the UI thread (catalogue load, dry runs and the transaction run on workers and
post results back to the main loop).

## Where it ships

- `daemonarchy-pkg` and its tests: this repository (`apps/daemonarchy-pkg/`), next to the
  SDK and the engine it shares; CI runs the headless tests here.
- Apps menu: `daemonarchy-pkg.desktop` (so the application launcher lists it) and the
  Omarchy menu entries **Install > Packages** and **Remove > Packages**
  (`omarchy-menu.jsonc` in daemonarchy-desktop) pointing at it, with OctoPkg kept as
  **… > Packages (OctoPkg)** until it is retired.
- Package: a `ports-mgmt/daemonarchy-pkg` port in daemonarchy-ports, built for amd64 on
  the build VM, added to the desktop's dependencies.

## Plan (small PRs)

1. This design.
2. Catalogue and plan layers with the engine contract and tests (fixtures: signed and
   unsigned repository configs, a captured plan, the retained MSI log for progress).
3. Transaction helper: identity check, event stream, retry, refusal tests.
4. GTK 4 window with palette, keyboard use, reduced motion; headless GTK tests under
   Xvfb or Broadway.
5. Desktop file, menu entries and the port.
6. Evidence: real install, update and remove on FreeBSD from a clean desktop, timing
   figures, and the failure cases (unreachable feed, wrong key, corrupt archive, full
   disk, cancelled prompt).

## What cannot be verified without hardware

The GTK window can be built and driven headless on a FreeBSD VM. Responsiveness on real
GPUs and the Hyprland compositor, real input devices and the login-session askpass
prompt need an installed desktop (MSI and MacBook). Packaging runs on the build VM; the
installed result is a physical check.

## Using the text commands

```
apps/daemonarchy-pkg/bin/daemonarchy-pkg repos                  # signed / unsigned / broken, with key fingerprints
apps/daemonarchy-pkg/bin/daemonarchy-pkg search editor
apps/daemonarchy-pkg/bin/daemonarchy-pkg plan install cowsay    # the dry run as a plan, with its identity
apps/daemonarchy-pkg/bin/daemonarchy-pkg --json plan remove cowsay
```

The window will call exactly these layers, so what the text commands print is what it shows.

## The transaction helper

`daemonarchy-pkg-helper ACTION --identity SHA256 [--allow-unsigned REPO]... NAME...` runs as root
(the window starts it with `sudo -A` through the desktop's askpass, else `sudo -n`). It
recomputes the plan and runs only if the identity is the one the user approved; a repository
without a verified signature must also be named. It then fetches with `parallel-fetch` (four
streams for pkg.FreeBSD.org, sixteen for the feeds, the installer's measured settings) and runs
pkg. Its output is the install log's vocabulary (`@@phase`, `@@plan`, `@@fetch`, pkg's
`[n/N]` lines) ending in one `@@result` line (`daemonarchy/gui-result@1`). Exit status: 0 done,
1 pkg failed, 3 refused (plan changed, or nothing to do), 4 refused (unsigned repository), 5 the
download cannot succeed. Retry runs the whole thing again, so it re-plans and reuses archives
already in pkg's cache.

It runs as root on arguments a user chose, so it accepts only plain package names, repository
names and a 64-hex identity, and has no option that points it at another database,
configuration directory, pkg or engine directory.
