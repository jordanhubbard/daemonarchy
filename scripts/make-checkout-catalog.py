#!/usr/bin/env python3
"""Combine verified builder receipts into the catalogue embedded in the ISO."""
import argparse
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory', type=Path)
parser.add_argument('--url', required=True)
parser.add_argument('--ports-tracking-branch', default='omarchy')
args = parser.parse_args()
if not re.fullmatch(r'https://github.com/jordanhubbard/daemonarchy/releases/download/[A-Za-z0-9._-]+', args.url):
    parser.error('Use a release-specific Daemonarchy package repository URL')
trees = {kind: json.loads((args.directory / (kind + '.json')).read_text()) for kind in ('ports', 'src')}
if not re.fullmatch(r'[A-Za-z0-9_.-]+', args.ports_tracking_branch) or '..' in args.ports_tracking_branch:
    parser.error('Invalid ports tracking branch')
trees['ports']['tracking_branch'] = args.ports_tracking_branch
for kind, tree in trees.items():
    assert re.fullmatch(r'[0-9a-f]{40}', tree['revision'])
    assert 1 <= tree['depth'] <= 100
    assert tree['parts']
    for part in tree['parts']:
        package = args.directory / (part['package'] + '.pkg')
        assert package.stat().st_size == part['download_bytes'], package
print(json.dumps(dict(schema=1, repository_url=args.url, trees=trees), indent=2))
