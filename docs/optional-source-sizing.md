# Optional ports and system source: space estimate

**Superseded by shallow live checkout packages (2026-10-13).** The original
measurements below exclude Git metadata. The installer now uses depth-1 Git
checkouts, with download and peak-space sizes from the generated `checkouts.json`
catalogue. See [the build and runtime instructions](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md#building-live-checkout-packages).
The seed packages contain no full historical repository; users can deepen
history explicitly with Git.

## Current 1.3.1 shallow packages

The checked-in [catalogue](../overlay/usr/local/share/daemonarchy-installer/checkouts.json)
is byte-identical to the one published with the
[1.3.1 checkout feed](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-amd64-1.3.1-r2)
(SHA-256 `c9909b88a6d9817ad01b2c96107b5a2eb2c67c3c993fe059e86b74134f89ca5c`).
It selects daemonarchy-ports `b785784219af455a9ce4fd70c59bc96ba77f469f` and
daemonarchy-src `d63d77f4eb3cc29e16510f7bdec73602e27c2844`, both on `main`. A
native FreeBSD `pkg` client accepted the feed's signed catalogue; see the
[1.3.1 release notes](release-1.3.1.md).

| Selection | Package download, bytes | Extracted content including `.git`, bytes | Peak free-space allowance, bytes |
| --- | ---: | ---: | ---: |
| Ports | 238,227,784 | 732,991,869 | 3,918,238,282 |
| System source | 718,019,739 | 1,932,460,458 | 6,930,664,679 |

<!-- release-sync: history -->
The earlier 1.1.1 catalogue selected ports `f7d7ee897405dcb8ce87e674588a4e1b3bfba00e`
on `daemonarchy-1.1.1` and source `bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf` from the
[1.1.1 checkout feed](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-bdcfeac3e1cb-f7d7ee897405-v1),
verified in [the 1.1.1 record](testing-1.1.1.md): ports 237,513,943 /
728,629,485 / 3,906,574,381 bytes and system source 716,771,851 /
1,930,848,921 / 6,923,737,608 bytes.
<!-- /release-sync -->

The allowances cover seed packages, assembly, extraction and allocation
headroom; they are additional to the desktop target minimum and exclude build
output. Existing working trees are preserved. These inputs supersede the dated
measurements below, which remain provenance rather than current package sizes.

## October 13 shallow live packages (historical)

Built on 2026-10-13. These figures include a depth-1 `.git` directory and a
complete working tree. Package seed archives and temporary extraction files are
included in the conservative peak allowance, but compiler output is not.

| Selection | Package download | Extracted file contents including `.git` | Peak free-space allowance |
| --- | ---: | ---: | ---: |
| Ports | 221.4 MiB | 0.67 GiB | 3.60 GiB (UI rounds to 4) |
| System source | 680.3 MiB | 1.80 GiB | 6.45 GiB (UI rounds to 7) |
| Both | 901.7 MiB | 2.47 GiB | 10.05 GiB |

File-content sizes are not filesystem allocation. The allowance includes
cached packages, installed seeds, the assembled archive, extracted contents,
per-file allocation and metadata headroom. The installer adds it to the base
20 GiB target minimum; both options therefore require just over 30 GiB before
any additional space for building software. Seed packages may be removed after
creation without touching the working checkouts.

The October 13 catalogue recorded exact revisions, sizes and payload hashes. Its ports used integration commit
`6fb491f4c73a49b71b4843bbe2fd267953a59bc1`; system sources used that image kernel's
`a52c50b4b7c2652954ef1bd34710a4b1fc8ef391`. Updating to a new release snapshot
requires rebuilding these packages and regenerating the catalogue.

## Original source-only estimate

Measured on 2026-10-12 for planning installer selections. The options were not
implemented at that planning checkpoint. They have since shipped as shallow
checkouts; these measurements are not fixed budgets for another CURRENT snapshot.

## Inputs and locations

- `/usr/ports`: a source-only archive of the Daemonarchy release ports tree,
  based on [jordanhubbard/freebsd-ports, branch `omarchy`](https://github.com/jordanhubbard/freebsd-ports/tree/omarchy).
  The published fork revision measured was
  `c9249ea1d16b911e5326c1509d8707a842bb7989`.
  The release archive should use the final package-compatible integration tree,
  including any Daemonarchy changes not yet pushed to the fork.
- `/usr/src`: sources matching the installed FreeBSD snapshot, following
  [FreeBSD CURRENT (`main`)](https://github.com/freebsd/freebsd-src/tree/main).
  This estimate uses the 2026-10-05 snapshot's source tree in the image build
  jail. At the measurement checkpoint the snapshot download endpoint reported `src.txz` as
  230,837,504 bytes. The cached snapshot MANIFEST records SHA-256
  `681c8a77d8ecd15ecdcc2e160e459adc2311e7457f0f5a81652c1cfce24d59f3`.
  The archive download was not completed or checksum-verified for this sizing
  exercise; installed sizes were measured directly from the existing jail tree.

The snapshot endpoint is mutable. Release artifacts must retain the matching
source archive, revision and checksum alongside the base/kernel sets. Do not
resolve a moving source or ports branch when the user installs an older image.

That historical table uses the image integration tree measured at
`6fb491f4c73a49b71b4843bbe2fd267953a59bc1`, rather than the slightly smaller
published fork tree.

## Measured sizes and planning allowance

All units below are binary (MiB = 2^20 bytes; GiB = 2^30 bytes).

| Selection | Compressed download | File contents | Estimated installed allocation | Suggested extra free space during installation |
| --- | ---: | ---: | ---: | ---: |
| Ports → `/usr/ports` | 99.5 MiB | 0.54 GiB | 1.29 GiB | 1.5 GiB |
| System source → `/usr/src` | 220.1 MiB | 1.43 GiB | 1.73 GiB | 2.5 GiB |
| Both | 319.7 MiB | 1.98 GiB | 3.02 GiB | 4.0 GiB |

The allowance is **additional to the desktop installation**, not a new total
minimum disk size. The allocation estimate rounds each regular file up to
4 KiB and allows 4 KiB per directory. This is a planning model, not a measured
ZFS allocation or a guaranteed upper bound: metadata, compression, record sizes,
snapshots and filesystem settings change actual use. The free-space allowances
include downloaded archives and headroom; remove temporary archives after
successful extraction. Recheck capacity against the final packaged artifacts.

Ports contain build recipes and patches, not all third-party source code.
These numbers exclude Git history, ports distfiles, installed build dependencies,
ports work directories, `/usr/obj`, and compiler outputs. Building software needs
additional space depending on the selected ports or system build.

## Measurement method

For ports, archive the exact commit without Git history or untracked work:

```sh
git -C /usr/ports archive --format=tar --prefix=usr/ports/ c9249ea1d16b911e5326c1509d8707a842bb7989 | gzip -n -6 > ports.tar.gz
```

The resulting archive is 103,677,791 bytes, SHA-256
`ce5c91382dac015e8c3d349be5e82dcc0b6046a04b70bb383f15407deae75695`.
Its 176,129 regular files contain 580,284,721 bytes, or 1,185,525,760
bytes after rounding each file to 4 KiB; there are 47,584 directories.

The measured historical image integration tree produced a 104,378,040-byte gzip archive,
SHA-256 `8b44685ccaef5ea256277764886787cfd88c66c17e55f20f84323e91a3a1f624`,
with 175,670 regular files, 582,023,043 content bytes, 1,185,865,728
bytes rounded per file to 4 KiB, and 47,613 directories. It was measured using
the same archive command with the integration-tree path and revision.

For source, walk the snapshot jail's `/usr/src` with `lstat`, excluding symlinks
from regular-file byte totals. Its 114,642 regular files contain 1,539,737,866
bytes, or 1,820,225,536 bytes rounded per file to 4 KiB; there are 9,857
subdirectories. The compressed size is the HTTP Content-Length of the matching
October 5 `src.txz`, not a newly built package size. A future `.pkg` wrapper or
different compressor will change download sizes.

## ISO impact

<!-- release-sync: history -->
This October 13 arithmetic is kept for provenance. The published 1.0.1 ISO is 1,834,121,216 bytes. Adding these two compressed
archives gives approximately 2,169,336,760 bytes (2.020 GiB), before additional
ISO metadata or other 1.1 changes. That exceeds the documented 2 GiB release
asset budget by about 20.8 MiB. This is arithmetic on the existing ISO, not a
new ISO build measurement.
<!-- /release-sync -->

Prefer downloading selected, pinned archives during installation; this adds
no archive payload to the ISO. Offer independent selections and verify their
checksums before extraction. Validate the final installation's actual disk use
and source/kernel identity before advertising these options as supported.
