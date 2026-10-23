# Native package resolution checks

`scripts/native-package-plan.py` compares a real native pkg dry-run with one
selection from a [pinned catalogue graph](package-dag.md). It copies only pinned
repository metadata into a fresh private case, initializes an empty private
database, verifies the package identities and dependency records imported by pkg,
and compares every proposed package version and repository with the graph.

This development probe uses unsigned, local frozen metadata. It observes native
resolution without granting package installation, authenticating a repository,
admitting final release inputs or issuing a Literate AI lifecycle receipt.
Signed repository acquisition, payload verification, transaction coordination,
safe parallel installation and native performance/recovery acceptance remain
required under PKG-001.

The separate [signed snapshot checker](signed-package-snapshot.md) now provides
native public-key catalogue and fetched-archive verification. Its observations
remain distinct from the unsigned development-plan probes below; a signed
snapshot does not silently promote a graph or authorize installation.

[The development checkpoint](../verification/native-package-plan-development.json)
binds 16 passing controller and native FreeBSD checks, exact tested code/pkg/
graph/metadata hashes, and actual desktop/NVIDIA plans matching all 952/960
package identities. Both private databases remain empty, both private caches
remain empty, and the host database bytes are unchanged. Native changed-version
and missing-transitive-package controls refuse without passing result records.
The recorded omarchy dependency/version difference is accepted by the real
native solver in these selected development plans. Earlier preparation failures
remain retained; no final release or signed-repository qualification follows.

## Reviewed inputs

Use the existing allocated native FreeBSD worker. Root ownership is required by
pkg for its private database; do not weaken ownership checks or use the physical
operator workstation as an aggregate build/test worker. Retain existing cases.
Use the reviewed source and the exact installed native pkg executable; the
executable must be root-owned and unwritable by other users. Its complete
SHA-256 pin is checked before and after the probe. This is an installed-tool
observation, not source-built toolchain or SDK admission.

Prepare a mode-0600 JSON input file beside the graph and metadata captures:

```json
{
  "schema": "daemonarchy/native-package-plan-inputs@1",
  "graph": {"path": "graph.json", "sha256": "<reviewed graph SHA-256>"},
  "pkg": {"path": "/usr/local/sbin/pkg", "sha256": "<reviewed executable SHA-256>"},
  "repositories": [
    {
      "id": "NativeCaptured",
      "files": {
        "meta.conf": {"path": "snapshot/meta.conf", "sha256": "<reviewed SHA-256>"},
        "packagesite.pkg": {"path": "snapshot/packagesite.pkg", "sha256": "<reviewed SHA-256>"},
        "data.pkg": {"path": "snapshot/data.pkg", "sha256": "<reviewed SHA-256>"}
      }
    }
  ]
}
```

Repository IDs must exactly match the graph's catalogue IDs. This adapter selects
the current three-file metadata format used by the tested native repository.
Other layouts require separate adaptation and qualification. Input paths may be
relative to the input file or absolute, but final path components cannot be
symlinks. Resolve a poudriere `.latest` selection to its actual retained files
before authoring the pins; never write through those links. The checker reads
the pinned bytes and copies them into the case before invoking pkg.

Select one named graph selection and a fresh absolute case directory:

```sh
sudo python3.12 scripts/native-package-plan.py /absolute/inputs.json \
  --sha256 <reviewed-input-file-sha256> \
  --selection desktop \
  --case /absolute/fresh-private-case
python3.12 tests/native-package-plan.py -v
```

The input file itself is pinned. There is no command to reuse an occupied case
or accept a mismatched plan. Each attempt uses case-local pkg configuration,
repositories, cache and database with automatic repository refresh and plugins
disabled. The only configured repository URLs are the copied local metadata;
the graph's transport URLs are not used. The installed host package database is
not an input to this empty-target plan.

## Observations and refusal

The native operations are metadata import, `pkg shell 'SELECT 1;'` to establish
the otherwise absent private SQLite file, and `pkg install -nUy -- <roots>`.
The dry-run flag prevents installation; the yes flag lets this pkg version
complete the dry-run with a successful exit. No package fetch, installation,
script or trigger operation is requested. Original metadata files remain intact.

For every selected package, compare the imported name, version, origin, ABI,
native archive checksum, repository path, download/installed sizes and complete
declared dependency records. Read the generated repository database through
SQLite's read-only connection mode. Its known current and preceding filesystem
layouts are recognized; unknown layouts refuse. A native proposal must have one
complete new-install section, consistent counts and exact expected package,
version and repository identities. Other actions, malformed/duplicate/omitted
entries, changed catalogue data and ambiguous repository attribution refuse.
Every native command requires zero exit and empty stderr. Printed partial output
or a successful plan's package count alone does not establish acceptance.

Command stdout/stderr stay in private case files. Each child has an internal
deadline; timeout or handled termination kills and reaps only its owned process
group, retaining partial output. Occupied logs refuse. Input failures may refuse
before case creation. Later failures leave the case and logs without a passing
`result.json`; none is interpreted as success.

The result binds the exact graph, input, native pkg version/binary and one
selection. `native_plan_matches_graph: true` means the native package/version/
repository proposal matched the graph and its imported identity/dependency
records. The private installed-package count must remain zero and the private
package cache must remain empty. `installation_authorized` and
`repository_signatures_qualified` remain false. The original graph is not mutated
or promoted to a lifecycle receipt. Native solver observations do not qualify
package side effects, kernel/module compatibility or real installed behavior.

The source behavior follows
[pkg's install implementation](https://github.com/freebsd/pkg/blob/main/src/install.c)
and [dry-run contract](https://github.com/freebsd/pkg/blob/main/docs/pkg-install.8).
