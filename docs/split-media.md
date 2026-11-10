# Split media transport (development)

A complete RAM-root installer can fit the existing raw-media budget while its
single `.iso.xz` exceeds the public-asset budget. `scripts/split-media.py` retains
the complete raw image in independent XZ parts, each containing at most 1 GiB of
raw bytes and checked to be strictly smaller than the existing 2 GiB asset limit.
No installer payload is removed or modified.

This is a development transport under ARM-005. The current release verifier,
fill/current-record tools and publication documentation still select single
image assets. They must explicitly admit the new format before publication.
Final source/world/ABI, signatures, native boot, installation, desktop, recovery,
physical hardware and lifecycle acceptance remain open. Existing release tags,
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
