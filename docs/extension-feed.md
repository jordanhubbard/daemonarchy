# Installer extension feed

Installer extensions (the four arcade games first) are **not** baked into the ISO. They are published as
compressed, content-identified, signed bundles on a GitHub release, listed by a signed compressed
index, and downloaded during the installation when the user chooses them. This page is the format and
the tooling; the installer side is described in [arcade-games.md](arcade-games.md).

## What is published

One versioned release per architecture and image version, never the latest release and never a tag that
already exists, named `extensions-<os>-<arch>-X.Y.Z` (for example `extensions-16-amd64-1.4.1`):

| Asset | What it is |
| --- | --- |
| `extensions-index.json.xz` | the index, xz-compressed |
| `extensions-index.json.xz.sig` | its detached signature |
| `ext-<id>-<version>.tar.xz` | one extension: a deterministic tar, xz-compressed |
| `ext-<id>-<version>.tar.xz.sig` | its detached signature |

**Everything is compressed**: bundles and index are xz, and the only other files are signatures. There is no
raw payload. `scripts/extension-bundle.py table DIR` prints compressed and uncompressed sizes. The
installer decompresses on the client, after verification.

## Index schema (`daemonarchy/extension-index@1`)

```json
{"schema": "daemonarchy/extension-index@1", "feed": "extensions-16-amd64-1.4.1", "arch": "amd64",
 "generated": "2026-10-30T00:00:00Z",
 "extensions": [{
   "id": "hordeshot", "name": "Hordeshot", "version": "1.0.0", "type": "game", "category": "Games",
   "description": "...", "capabilities": ["draw", "input", "audio"], "min_size": [50, 24], "api": "1.3",
   "bundle": {"file": "ext-hordeshot-1.0.0.tar.xz", "bytes": 3141, "sha256": "...",
              "raw_bytes": 10240, "raw_sha256": "..."}}]}
```

`type` is one of `game`, `tool`, `animation`, `visualizer`; `category` follows it (Games, Tools, Visuals).
`capabilities` is a subset of `draw`, `input`, `audio` and `window` that includes `draw`; `window` allows the
extension to ask the host for extra windows (see [visual-sdk.md](visual-sdk.md)). The index states the same
facts as the extension's own `manifest.json` (schema `daemonarchy/extension@1`), and the installer refuses a
bundle whose manifest disagrees with the signed index.

## Signing and the trust anchor

Each signature is an `openssl dgst -sha256` signature over the compressed file's bytes. The installer
verifies against the **public key the image already pins for its package repository**
(`/usr/local/share/daemonarchy-installer/daemonarchy.pub` on the live image), so there is no new trust
anchor, and uses only `openssl`, which the base system provides. The index is signed, and so is every bundle;
the index also carries each bundle's size and SHA-256, so a bundle is checked three ways.

## What the installer checks, in order, before anything runs

1. the index signature, then its schema, its feed name (it must be the feed this image expects) and every
   entry's shape;
2. for the bundle the user chose: its size against the index (while downloading too, so an oversized download
   is stopped), then its SHA-256 and signature;
3. decompression bounded by the declared uncompressed size (a small file cannot expand without limit), then the
   uncompressed SHA-256;
4. extraction: only regular files in the one directory named by the extension's id, no links, devices, absolute,
   backslash or parent paths, no nested directories, at most 64 files of at most 4 MiB, modes reset to 0644;
5. the extracted manifest agrees with the signed index (id, name, version, type, capabilities, API, minimum
   size) and the entry file's hash matches the manifest.

Downloads are `https` only (plain `http` only to loopback, for tests). Offline or unreachable, the installer
says so and runs nothing.

## The install trace

Each download appends an `ext_fetch` event to the installer trace ([install-trace.md](install-trace.md))
with the file `name`, compressed `bytes`, `dur_us` and `status`.

## Building, signing, verifying, staging

```
scripts/extension-bundle.py stage SRC... --out DIR --feed extensions-16-amd64-1.4.1 --arch amd64 \
    --key PRIVATE_KEY --pubkey PUBLIC_KEY        # build + sign + verify + print the asset table
scripts/extension-bundle.py sign   DIR --key RELEASE_KEY   # re-sign a staged feed: only .sig files change
scripts/extension-bundle.py verify DIR --pubkey PINNED_PUB --feed extensions-16-amd64-1.4.1
scripts/extension-bundle.py table  DIR
```

Each `SRC` is an extension directory with a sealed `manifest.json` (`scripts/seal-games.py` seals the game
sources). Packing is deterministic: sorted, mtime 0, owner 0, normalised modes. The tool never uploads.
Staging with a throwaway key and re-signing with the release key leaves every hash in the index unchanged.

## Publishing checklist

1. Build and stage the feed in a scratch directory; sign it with the key whose public half is the image's
   pinned repository key; `verify` it with that public key and the expected feed name.
2. Record the asset table (names, compressed and uncompressed sizes, SHA-256) in the release record.
3. Create a **non-latest** release with the new, unused tag and upload exactly the assets above. Do not touch
   an existing release or the latest release.
4. Install from a test image against the published feed (download, verify, run), with the network blocked once
   to confirm the offline message.
