# Closure feed records

Each `TAG.json` is the `closure_feeds` entry list for one published closure feed
shard: its release tag and the size and SHA-256 of every asset, in the form
`scripts/verify-release-assets.py` reads (`[size, "sha256:..."]`). It is generated
from the staged manifest, not written by hand:

```
python3 scripts/package-feed-stage.py record --out DIR     # DIR holds TAG.manifest.json
```

A release-inputs record (`verification/release-<version>.json`) copies these entries
into its `closure_feeds` field; from 1.4.1 the verifier refuses a record without them.

| Record | What it is |
| --- | --- |
| `packages-16-amd64-1.4.1-upstream` | The signed upstream snapshot of the amd64 installer closure: the 786 FreeBSD packages (3.49 GiB) the ISO's own packages and our application feed do not carry, plus the catalogue (`data.pkg`, `packagesite.pkg`, `meta`, `meta.conf`): 790 assets, 3,751,899,650 bytes, all zstd except the two 168-byte pkg config files. Signed with the release pkg repository key (public key SHA-256 `67986b40…74ef7`). Upstream FreeBSD builds redistributed unchanged; the licence review is open (PKG-002). |

**Published 2026-10-30** as its own non-latest release, `packages-16-amd64-1.4.1-upstream`
(not a draft; `daemonarchy-1.4.0` is still the latest release). `package-feed-upload.py
verify` re-downloaded and hashed all 790 assets against this record's manifest and
passed. Publishing the feed is not a release: no 1.4.1 image or release exists yet.

Upstream can move before the image is built. If a package the closure needs
changes or goes, stage the next snapshot as a new tag (never edit a published one) and
record it here.
