#!/usr/bin/env python3
"""Seal the installer's game plugins: manifest entry hashes and the trusted index.

  seal-games.py          rewrite each manifest's entry_sha256 and index.json
  seal-games.py --check  fail if either is stale (run by CI)

The index is what a Registry trusts: it names the SHA-256 of every manifest, and each
manifest names the SHA-256 of its entry file. Change a game, run this, commit the result.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "overlay/usr/local/lib/daemonarchy-visual"))
from daemonarchy_visual import plugin  # noqa: E402

GAMES = ROOT / "overlay/usr/local/share/daemonarchy-games"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        registry = plugin.Registry(str(GAMES))
        for name, reason in sorted(registry.refused.items()):
            print(f"{name}: {reason}", file=sys.stderr)
        if registry.refused or not registry.plugins:
            print("run scripts/seal-games.py and commit the result", file=sys.stderr)
            return 1
        print(f"{len(registry.plugins)} game plugins sealed: {', '.join(sorted(registry.plugins))}")
        return 0
    for directory in sorted(p for p in GAMES.iterdir() if (p / "manifest.json").is_file()):
        plugin.seal_manifest(str(directory))
    plugin.write_index(str(GAMES))
    return main_check()


def main_check():
    sys.argv = [sys.argv[0], "--check"]
    return main()


if __name__ == "__main__":
    raise SystemExit(main())
