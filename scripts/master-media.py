#!/usr/bin/env python3
"""Verify or reconstruct explicitly selected mastering media; no native admission."""
import argparse
import importlib.util
import json
import lzma
from pathlib import Path
import re
import sys

RAW_LIMIT = 3758096384


def selected(manifest, pin, image, output=None):
    if not re.fullmatch(r"daemonarchy-(?:hwtrace-)?[0-9]+\.[0-9]+\.[0-9]+-(?:amd64|aarch64)\.(?:iso|img)", image):
        raise ValueError("expected a canonical release image selection")
    version = re.search(r"([0-9]+\.[0-9]+\.[0-9]+)-", image).group(1)
    if tuple(map(int, version.split("."))) < (1, 6, 0):
        raise ValueError("split mastering begins with 1.6.0")
    spec = importlib.util.spec_from_file_location("master_split_codec", Path(__file__).with_name("split-media.py"))
    media = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(media)
    record = media.load_manifest(manifest, pin)
    if record["image"]["name"] != image:
        raise ValueError("manifest differs from the selected release/architecture image")
    if not 0 < record["image"]["bytes"] < RAW_LIMIT:
        raise ValueError("raw image exceeds the unchanged mastering media budget")
    if output is None:
        return media.stream_image(manifest, pin)
    return media.join(manifest, pin, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        record = selected(args.manifest, args.sha256, args.image, args.out)
    except (OSError, ValueError, lzma.LZMAError) as exc:
        print(f"master-media: {exc}; failed outputs remain private", file=sys.stderr)
        return 1
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
