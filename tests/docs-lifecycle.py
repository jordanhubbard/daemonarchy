#!/usr/bin/env python3
"""Keep the documentation graph acceptable to the Literate AI authority gate.

`litai verify` fails closed on three things this repository broke in 1.4.1: a detailed
roadmap without the lifecycle header (`Status`, one `Owning queue item` link into
active-work.md, `Completion / archival evidence`), a link fragment that does not match
the framework's heading slug (it collapses whitespace, so `### X — Y` is `#x-y`, not
GitHub's `#x--y`), and a Markdown file under docs/ that cannot be reached by links from
SKILL.md. These checks mirror those rules without the framework, so they run in plain CI.

Run `python3 tests/docs-lifecycle.py -v`. The separate `authority-reviewed` marker in
docs/architecture/design-traceability.md is a human attestation and is not checked here.
"""

from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
QUEUE = DOCS / "roadmap/active-work.md"
STATES = {"active", "partial", "deferred", "completed", "historical"}
FIELD = re.compile(
    r"^ {0,3}-[ \t]+\*\*(Status|Owning queue item|Completion / archival evidence):\*\*"
    r"[ \t]+(.+?)[ \t]*$"
)
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")


def slug(heading):
    heading = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    heading = heading.replace("`", "").replace("*", "").casefold()
    heading = re.sub(r"[^\w\-\s]", "", heading).strip()
    return re.sub(r"\s+", "-", heading)


def anchors(text):
    found, counts, fence = set(), {}, False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        match = None if fence else re.match(r"^ {0,3}#{1,6}[ \t]+(.+?)[ \t#]*$", line)
        if match:
            base = slug(match.group(1))
            n = counts.get(base, 0)
            counts[base] = n + 1
            found.add(base if n == 0 else f"{base}-{n}")
    return found


def header(text):
    fields = {}
    for line in text.splitlines():
        if re.match(r"^ {0,3}##(?:[ \t]+|$)", line):
            break
        match = FIELD.match(line)
        if match:
            fields[match.group(1)] = match.group(2)
    return fields


def roadmap_docs():
    return sorted(p for p in (DOCS / "roadmap").glob("*.md") if p != QUEUE)


class RoadmapLifecycle(unittest.TestCase):
    def test_every_detailed_roadmap_has_a_valid_header(self):
        queue = anchors(QUEUE.read_text(encoding="utf-8"))
        for path in roadmap_docs():
            with self.subTest(path.name):
                fields = header(path.read_text(encoding="utf-8"))
                for name in ("Status", "Owning queue item", "Completion / archival evidence"):
                    self.assertIn(name, fields)
                self.assertIn(fields["Status"], STATES)
                links = LINK.findall(fields["Owning queue item"])
                self.assertEqual(len(links), 1, "exactly one owning link")
                split = urlsplit(links[0])
                self.assertEqual(split.path, "active-work.md")
                self.assertIn(unquote(split.fragment), queue)
                if fields["Status"] in {"completed", "historical"}:
                    self.assertTrue(LINK.findall(fields["Completion / archival evidence"]))


class LinkFragments(unittest.TestCase):
    def test_active_work_fragments_resolve(self):
        queue = anchors(QUEUE.read_text(encoding="utf-8"))
        for path in sorted(DOCS.rglob("*.md")):
            for target in LINK.findall(path.read_text(encoding="utf-8")):
                split = urlsplit(target)
                if split.scheme or not split.fragment:
                    continue
                dest = (path.parent / split.path).resolve() if split.path else path
                if dest == QUEUE:
                    with self.subTest(f"{path.relative_to(ROOT)} -> #{split.fragment}"):
                        self.assertIn(unquote(split.fragment), queue)


class Reachability(unittest.TestCase):
    def test_every_doc_is_linked_from_the_index(self):
        seen, todo = set(), [DOCS / "README.md"]
        while todo:
            path = todo.pop()
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            for target in LINK.findall(path.read_text(encoding="utf-8")):
                split = urlsplit(target)
                if split.scheme or not split.path.endswith(".md"):
                    continue
                todo.append((path.parent / split.path).resolve())
        missing = [
            p.relative_to(ROOT).as_posix()
            for p in sorted(DOCS.glob("*.md"))
            if p.resolve() not in seen and p.name != "README.md"
        ]
        self.assertEqual(missing, [], "docs not reachable from docs/README.md")


if __name__ == "__main__":
    unittest.main()
