#!/usr/bin/env python3
"""Scrub a retained Daemonarchy install log before it becomes a test fixture.

Removes or generalizes anything that could identify a person, machine or
network: account names, home paths, e-mail addresses, IPv4/IPv6 and MAC
addresses, Wi-Fi network names, long hexadecimal digests and UUIDs, random
temporary-file suffixes, and firmware boot entries for other operating
systems. Installer markers, package names and pkg's counters are kept,
because the replay tests depend on them. Prints a JSON summary of each rule's
replacement count.
"""
import json
import re
import sys

RULES = (
    ('email', re.compile(r'\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b'), 'user@example.invalid'),
    ('mac', re.compile(r'\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b'), '00:00:00:00:00:00'),
    ('ipv6', re.compile(r'\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}\b'), '2001:db8::1'),
    ('ipv4', re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), '192.0.2.1'),
    ('uuid', re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'),
     '00000000-0000-0000-0000-000000000000'),
    ('digest', re.compile(r'\b[0-9a-fA-F]{32,}\b'), lambda m: '0' * len(m.group(0))),
    ('temporary', re.compile(r'(/tmp/[\w.-]+?\.)[A-Za-z0-9]{6,12}\b'), r'\1XXXXXXXX'),
    ('home', re.compile(r'/home/[^/\s:]+'), '/home/user'),
    ('ssid', re.compile(r'((?:ssid|SSID)[=:" ]+)"?[^"\s]+"?'), r'\1"network"'),
    ('boot-entry', re.compile(r'^([ +]Boot[0-9A-F]{4}\*) (?!Daemonarchy).*$'), r'\1 Other boot entry'),
)


# pkg prints package versions that look like IPv4 addresses (gcr 4.4.0.1);
# address rules skip pkg's own package rows.
PACKAGE_ROW = re.compile(r'^(?:\t|\[\s*\d+/\d+\] |Fetching |Installing |Extracting |Upgrading )')
ACCOUNT = re.compile(r'^((?:\x1b\[[0-9;]*m)?==>(?:\x1b\[[0-9;]*m)? Configuring )\S+')


def scrub(text, usernames=()):
    counts = {name: 0 for name, _pattern, _replacement in RULES}
    counts['account'] = 0
    output, after_user_phase = [], False
    for line in text.splitlines(keepends=True):
        for name, pattern, replacement in RULES:
            if name in ('ipv4', 'ipv6') and PACKAGE_ROW.match(line):
                continue
            line, count = pattern.subn(replacement, line)
            counts[name] += count
        if after_user_phase:
            # The user phase announces the account name on its next line.
            line, count = ACCOUNT.subn(r'\1user', line)
            counts['account'] += count
        after_user_phase = line.startswith('@@phase user')
        output.append(line)
    text = ''.join(output)
    for user in usernames:
        text, count = re.subn(rf'\b{re.escape(user)}\b', 'user', text)
        counts[f'username:{len(user)}'] = count
    return text, counts


def main(argv):
    if len(argv) < 3:
        print('Usage: scrub-install-log.py INPUT OUTPUT [USERNAME...]', file=sys.stderr)
        return 2
    with open(argv[1], encoding='utf-8', errors='replace', newline='') as stream:
        text = stream.read()
    text, counts = scrub(text, argv[3:])
    with open(argv[2], 'w', encoding='utf-8', newline='') as stream:
        stream.write(text)
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
