"""The repositories pkg is configured with, and whether each one is signed.

pkg reads /etc/pkg/*.conf and then ${LOCALBASE}/etc/pkg/repos/*.conf (REPOS_DIR); a repository
named in a later file is merged over the earlier one of the same name, and `enabled: no` switches one
off. This reads the same files with the same rules, enough of UCL for what repositories use:
`Name: { key: value; ... }`, quoted or bare values, # and // comments.

A repository is **signed** when signature_type is `pubkey` (with a key file that exists) or
`fingerprints` (with a directory holding at least one trusted fingerprint). It is **unsigned**
when there is no signature_type or it is `none`, and **broken** when it names a key that is not
there: pkg would refuse it, so the plan must not pretend it is trusted.
"""
import hashlib
from pathlib import Path
import re

DEFAULT_DIRS = ('/etc/pkg', '/usr/local/etc/pkg/repos')
SIGNED, UNSIGNED, BROKEN = 'signed', 'unsigned', 'broken'


class Repository:
    def __init__(self, name, fields, source=''):
        self.name, self.fields, self.source = name, fields, source
        self.url = fields.get('url', '')
        self.enabled = fields.get('enabled', 'yes').lower() in ('yes', 'true', 'on', '1')
        self.priority = int(fields['priority']) if fields.get('priority', '').lstrip('-').isdigit() else 0
        self.signature_type = fields.get('signature_type', 'none').lower()
        self.key = fields.get('pubkey') or fields.get('fingerprints') or ''
        self.trust, self.fingerprint, self.problem = self.judge()

    def judge(self):
        kind = self.signature_type
        if kind == 'pubkey':
            try:
                data = Path(self.key).read_bytes()
            except OSError:
                return BROKEN, '', f'the public key {self.key or "(not named)"} cannot be read'
            return SIGNED, hashlib.sha256(data).hexdigest(), ''
        if kind == 'fingerprints':
            trusted = Path(self.key) / 'trusted'
            try:
                files = sorted(p for p in trusted.iterdir() if p.is_file())
            except OSError:
                files = []
            if not files:
                return BROKEN, '', f'no trusted fingerprints in {trusted}'
            digest = hashlib.sha256(b''.join(p.read_bytes() for p in files)).hexdigest()
            return SIGNED, digest, ''
        return UNSIGNED, '', 'packages from this repository carry no signature check' if kind in ('none', '') else \
            f'unknown signature_type {kind!r}'

    @property
    def signed(self):
        return self.trust == SIGNED

    def describe(self):
        return dict(name=self.name, url=self.url, enabled=self.enabled, priority=self.priority,
                    trust=self.trust, signature_type=self.signature_type,
                    fingerprint=self.fingerprint[:16], problem=self.problem)


def tokens(text):
    """(kind, value) for words, quoted strings and the punctuation { } : , ; = in UCL-ish text."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == '#' or text.startswith('//', i):
            while i < n and text[i] != '\n':
                i += 1
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == '\\' else 1
            out.append(('str', text[i + 1:j]))
            i = j + 1
        elif c in '{}:,;=[]':
            out.append((c, c))
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '{}:,;="#[]':
                j += 1
            out.append(('word', text[i:j]))
            i = max(j, i + 1)
    return out


def parse(text):
    """{name: {key: value}} for the top-level `Name: { ... }` blocks of one repository file."""
    toks, found, i = tokens(text), {}, 0
    while i < len(toks):
        if (toks[i][0] in ('word', 'str') and i + 2 < len(toks) and toks[i + 1][0] == ':'
                and toks[i + 2][0] == '{'):
            name, i, fields = toks[i][1], i + 3, {}
            depth = 1
            while i < len(toks) and depth:
                kind = toks[i][0]
                if kind == '{':
                    depth += 1
                elif kind == '}':
                    depth -= 1
                elif (depth == 1 and kind in ('word', 'str') and i + 2 < len(toks)
                      and toks[i + 1][0] in (':', '=') and toks[i + 2][0] in ('word', 'str')):
                    fields[toks[i][1]] = toks[i + 2][1]
                    i += 2
                i += 1
            found[name] = fields
        else:
            i += 1
    return found


def configured_dirs(env=None):
    """Where the window looks: pkg's directories, or DAEMONARCHY_PKG_REPOS_DIRS (colon separated) for a test
    or a trial. Only the user's own window reads this; the root helper never does."""
    import os
    value = (os.environ if env is None else env).get('DAEMONARCHY_PKG_REPOS_DIRS', '')
    return tuple(d for d in value.split(':') if d) or DEFAULT_DIRS


def read(dirs=DEFAULT_DIRS):
    """The repositories in effect, in pkg's order: later files merge over earlier ones of the same name,
    then highest priority first (pkg prefers the higher number), then name for a stable list."""
    merged = {}
    for directory in dirs:
        try:
            files = sorted(Path(directory).glob('*.conf'))
        except OSError:
            continue
        for path in files:
            try:
                text = path.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            for name, fields in parse(text).items():
                # UCL merges objects, so `FreeBSD: { enabled: no }` in the local directory switches the
                # system repository off and keeps its url and keys.
                merged[name] = (dict(merged[name][0], **fields), str(path)) if name in merged else (fields, str(path))
    repos = [Repository(name, fields, source) for name, (fields, source) in merged.items()]
    return sorted(repos, key=lambda r: (-r.priority, r.name))
