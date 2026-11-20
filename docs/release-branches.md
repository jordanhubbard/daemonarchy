# Release branches and forward ports

Owned `main` contains the cumulative general changes from every release tip.
The upcoming Daemonarchy release uses `release/1.6` in these owned repositories:

| Repository | Cumulative development | Upcoming release |
| --- | --- | --- |
| jordanhubbard/daemonarchy | main | release/1.6 |
| jordanhubbard/daemonarchy-src | main | release/1.6 |
| jordanhubbard/daemonarchy-ports | main | release/1.6 |
| jordanhubbard/daemonarchy-desktop | main | release/1.6 |
| jordanhubbard/omarchy | main | release/1.6 |
| jordanhubbard/omarchy-freebsd | main | release/1.6 |

The owned Omarchy fork retains `quattro` as its default upstream channel; its
owned `main` starts at the same owned tip. Review upstream refreshes into owned
`main` and the release branch separately. FreeBSD pristine upstream refs and
feature, experiment or draft branches are not release branches and are not
admitted to `main` merely because they exist.

## Change flow

1. Land general development and fixes through a reviewed topic branch into
   owned `main`, with the owning repository's checks.
2. Backport selected changes through a release-targeted pull request. Preserve
   the original commit identity when possible; a cherry-picked equivalent patch
   is also recognized by the audit. A release branch need not contain newer
   development intended for the next release.
3. If an urgent fix lands on a release first, pair it with a forward port to
   `main`. Merge non-conflicting general changes; resolve conflicts explicitly
   and run the affected target's checks. A conflict is pending work, not an
   implicit release-only exception.
4. A workaround that must stay confined to that release needs both trailers
   below in its own commit message. Keep general fixes in separate commits.
   Do not rewrite published commits to add a retrospective exception.
5. Before a release or declaring integration complete, refresh all owned refs
   and run the audit. Any missing ordinary change blocks that declaration.
   Qualification still pins full commit identities, not moving branch names.

For example, a temporary ABI workaround confined to this release ends with:

```text
Daemonarchy-Release-Only: 1.6
Daemonarchy-No-Forward-Port: Temporary ABI workaround; the next release uses the new ABI and must not retain this path.
```

The version must match the release branch, and the reason must explain the
technical restriction. A generic “workaround” subject, an unmarked conflict,
or a release-related filename does not authorize omission from `main`.
Commit messages remain review authority; a trailer is not a waiver of testing.

## Audit

`release/branches.json` registers the six owned repositories and required
upcoming release branch. `scripts/check-release-branches.py` reads Git objects
without editing worktrees or refs. Fetch complete owned branch histories before
running it (a shallow history is insufficient):

```sh
git fetch --no-tags origin '+refs/heads/*:refs/remotes/origin/*'
python3 /path/to/daemonarchy/scripts/check-release-branches.py \
  --only daemonarchy-src --repo daemonarchy-src=/path/to/daemonarchy-src
```

Omit `--only` and supply six `--repo NAME=PATH` bindings for a full audit.
The checker requires `main` and `release/1.6`, examines all `release/*` tips plus
registered legacy release names, recognizes patch-equivalent cherry-picks,
and reports qualified exceptions separately. Unforwarded changes and unreviewed
merge resolutions fail. Unique merge resolutions are conservatively flagged
even if a maintainer believes an equivalent resolution already exists; reconcile
the history explicitly. It does not silently use an `ours` merge to mark work
as integrated.

The product's **Release branch synchronization** workflow runs the audit across
all six repositories hourly and on demand, and runs policy regression tests on
policy changes. GitHub ancestry comparisons handle the common case; only
branches with divergence require downloading history for a patch and exception
audit. This is a read-only drift alarm. It does not automatically merge
code, grant a style exception, enforce branch protection in another repository,
or assert native or hardware qualification. Paired review and forward-port work
remain part of completing every release repair. The initial November 20 audit
found every historical release tip already ancestral to its owned `main`.
The new release branches are development lines, not a declaration that 1.6 is
qualified or published.
