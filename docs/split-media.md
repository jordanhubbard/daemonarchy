# Split media transport (development)

A complete RAM-root installer can fit the existing raw-media budget while its
single `.iso.xz` exceeds the public-asset budget. `scripts/split-media.py` retains
the complete raw image in independent XZ parts, each containing at most 1 GiB of
raw bytes and checked to be strictly smaller than the existing 2 GiB asset limit.
No installer payload is removed or modified.

This is a development transport under ARM-005. The staged release verifier and
fill/current-record tools accept an explicit split selection from planned 1.6.0
onward. Existing release records retain their original single-image semantics.
Mastering/QA/device-writing integration and final source/world/ABI, signatures,
native boot, installation, desktop, recovery, physical hardware and lifecycle
acceptance remain open. Existing release tags,
asset bytes and size gates are unchanged.

Use a regular `.iso` or `.img` and its SHA-256 from the selected build/input
record. The output directory must not already exist. For example, set
`MEDIA_RAW_SHA256` from that record, then run:

```sh
sh scripts/check-image-size.sh /path/candidate.iso
python3 scripts/split-media.py pack /path/candidate.iso \
  --sha256 "$MEDIA_RAW_SHA256" --out /path/new-parts
```

Packing streams the image through bounded compression and independently decodes
all resulting parts before writing the manifest. The compressed manifest records
the complete raw-image identity and every part's name, compressed/raw sizes and
hashes. Its checksum sidecar follows the existing checksum-file convention.
Both image and manifest names remain independent of any publication or support
claim. The tool supports at most 64 parts, a 1 MiB manifest and a 128 MiB decoder
memory budget; it does not change the raw-media budget.

Obtain `MEDIA_MANIFEST_SHA256` from the reviewed packing result or approved
release record. A checksum downloaded beside arbitrary media is not its own
trust authority. Verify all bytes and reconstruct a new regular file with:

```sh
python3 scripts/split-media.py verify /path/new-parts/candidate.iso.parts.json.xz \
  --sha256 "$MEDIA_MANIFEST_SHA256"
python3 scripts/split-media.py join /path/new-parts/candidate.iso.parts.json.xz \
  --sha256 "$MEDIA_MANIFEST_SHA256" --out /path/new-reconstructed.iso
```

The verifier checks the full raw-image hash, part order/geometry, compressed and
raw hashes, exact family of files and checksum sidecar. It rejects unsafe names,
symlinks/nonregular files, duplicate or unknown manifest fields, oversized
expansion, trailing/concatenated streams and missing or extra parts. Other image
families may coexist in the same directory.

Joining requires a working filesystem with hardlink support. It writes a private
temporary file and publishes its final name exclusively
only after every check passes. Existing files and devices cannot be overwritten.
Failed pack directories and failed private reconstruction files are retained for
diagnosis and are not admitted media. Flashing a device is a separate operator
step after raw-media and artifact/target checks; this tool does not write devices.

Run `python3 tests/split-media.py -v` for real codec, reconstruction, tamper and
refusal controls. Full-sized retained-image results establish transport identity
only; they cannot qualify a different rebuilt final image.

## Staging a planned release

Name the raw file for its selected release, architecture and image product before
packing, for example `daemonarchy-1.6.0-aarch64.iso`. Stage the manifest, its
checksum sidecar and every part beside the other release assets. Do not also
stage a competing single-file image for that product. Keep the approved manifest
pin separate from the downloaded files.

After preparing a release draft, add the following explicit selection to the
normal `scripts/fill-release.py` invocation:

```sh
--split-image "aarch64=$MEDIA_MANIFEST_SHA256"
```

The repeatable kinds are `amd64`, `aarch64`, `hwtrace-amd64` and
`hwtrace-aarch64`. Each pin selects exactly one manifest. Authoring independently
streams the complete raw image before writing records. It records
`image_transports[logical-image]` with `format: "xz-parts@1"`, ordered part names,
the manifest name and the complete raw-image size/SHA-256. The asset map contains
the actual public manifest, sidecar and parts. The logical `.iso.xz`/`.img.xz`
name identifies the image product; it is not a downloadable asset.

Split templates must replace the ambiguous `*_BYTES` and `*_SHA256` tokens with
`*_MANIFEST`, `*_MANIFEST_BYTES`, `*_MANIFEST_SHA256`, `*_RAW_BYTES`,
`*_RAW_SHA256`, `*_DOWNLOAD_BYTES` and `*_PARTS_TABLE` as needed. The prefix is
`AMD64_ISO`, `AARCH64_ISO`, `HWTRACE` or `HWTRACE_AARCH64`. The table carries
individual public URLs, compressed sizes and hashes; download bytes sum the
compressed parts. The raw hash identifies the reconstructed media. Old ambiguous
tokens cause refusal before tracked files are written.

`verify-release-assets.py` requires the approved transport descriptor, exact
physical assets and raw identity, and retains the signed-boot, certificate and
package-closure gates. `release-current.py update` reads published GitHub assets
and additionally requires the matching approved release-input record for split
media. It preserves raw/part metadata in current and historical image records;
`check-published` rejects metadata drift as well as uploaded-asset drift.
Document checks reject nonexistent single-file download URLs and wrong part
sizes/hashes. These identity checks do not replace target qualification.

Run `tests/release-split-media.py` and `tests/release-split-flow.py` alongside the
codec controls. They use scratch fixtures and mocked publication metadata; they
do not publish, sign or establish native/hardware acceptance. The full-size
[retained-media control](../verification/split-media-development-20261110.json)
reconstructed 3,732,947,456 bytes in four independently verified parts. Its
source was an earlier retained installer/world, not the refreshed final release.
