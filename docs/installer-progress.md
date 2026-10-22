# Installer progress

The dashboard reports completed storage-preparation milestones and release archive
extractions, download completions reported by native pkg, and the package position
being processed. It does not turn elapsed time into a completion percentage. A
full meter describes only its labelled measurement; installation succeeds only
when the installer writes its successful result after the required checks.

Choose `DAEMONARCHY_PROGRESS_STYLE=bars`, `spectrum`, or `scope` before launching
the installer. Spectrum and scope trace measured counter changes, not a simulated
activity signal. `plain` emits readable status lines without terminal controls.
Non-terminal output and `TERM=dumb` also select plain output. Set
`DAEMONARCHY_REDUCED_MOTION=1` for static bars and `NO_COLOR=1` to disable color.
The display reflows on resize, clips to small terminals and restores the cursor
on exit or interruption. Color uses the native 16-color palette, or 256 colors
when the terminal declares that support. The original logo remains on terminals
large enough to show it; serial VT100 terminals use ASCII presentation.

The dashboard reads incrementally with bounded read and line sizes. Stalled input
keeps its last observed count and says it is waiting for another report. Invalid
measurements and truncated/replaced logs are visible; they cannot become a
passing progress record. An unavailable Python interpreter selects a passive
plain-log fallback that waits for the installer's actual result.

An optional authenticated-acquisition journal uses the existing
[package-engine event contract](https://github.com/jordanhubbard/daemonarchy/blob/feat/native-release-program/components/package-engine/interfaces/contract.md).
Pass its file with `--events`, together with the exact `--input-pin` and
`--repository-pin` SHA-256 values from the selected transaction. Journal events
must be ordered and preserve those pins. Verified archive bytes are neither
network throughput nor installed-package counts, and acquisition never authorizes
installation. Connecting the complete final-release planner/GUI and qualifying
physical-console installation remain open under UI-001 and PKG-001.

`PYTHONDONTWRITEBYTECODE=1 python3 tests/installer-progress.py` exercises the
read-only observer, bounded log backlog, failure handling and real kernel PTYs,
including resize, reduced motion, all styles/color modes and signal cleanup. It
does not partition storage, run pkg, or qualify a final installed system.
