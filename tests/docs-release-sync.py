#!/usr/bin/env python3
"""Keep current-state documentation in step with the latest published release.

`release/current.json` is the single source of truth for the latest published
stable release: version, tag, every published image type and the exact public
asset names, sizes and SHA-256 digests. The release procedure in HACKING.md
updates it first, from the verified published GitHub release; these checks then
fail until every current-state document agrees with it.

Historical documents keep their versions. A document is historical when it
matches HISTORICAL below or carries `<!-- release-sync: historical -->` in its
first lines. Inside a current-state document, a passage between
`<!-- release-sync: history -->` and `<!-- /release-sync -->` is history too.

Run `python3 tests/docs-release-sync.py -v`. It needs no network; use
`python3 scripts/release-current.py check-published` to compare the source of
truth itself with GitHub.
"""

from fnmatch import fnmatch
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "release/current.json"

# Documents describing the product as it is now: install procedure, download,
# hardware support, features, build and release instructions, and the docs
# shipped on the image.
CURRENT_STATE = (
    "README.md",
    "HACKING.md",
    "PROJECT.md",
    "ROADMAP.md",
    "SKILL.md",
    "AGENTS.md",
    "docs/*.md",
    "docs/architecture/*.md",
    "components/**/*.md",
    "secureboot/**/*.md",
    "overlay/**/*.md",
    "overlay/**/*.txt",
)

# Records that keep the versions they describe. Each entry says why.
HISTORICAL = {
    "docs/testing-*.md": "dated test and qualification records",
    "docs/release-*.md": "release notes; the current release's notes stay checked",
    "docs/package-repository-key-rotation-*.md": "per-release key rotation record",
}

MARKER = "<!-- release-sync: historical -->"
HISTORY_OPEN = "<!-- release-sync: history -->"
HISTORY_CLOSE = "<!-- /release-sync -->"

SHA = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
IMAGE = re.compile(
    r"daemonarchy-(?:[a-z][a-z0-9]*-)*?(\d+\.\d+\.\d+)(?:-[a-z0-9]+)*\.(?:iso|img)(?:\.xz)?(?![\w.])"
)
# A product version such as 1.3.1 or 1.4, not part of a name, path, address or
# FreeBSD branch (16.0).
VERSION = re.compile(r"(?<![\w.\-/@])([1-9])\.(\d+)(?:\.(\d+))?(?![\w\-]|\.\d)")
CURRENT_CLAIM = re.compile(
    r"\b(?:[Cc]urrent(?:ly)?|[Ll]atest|covers Daemonarchy|now ships)\b(?!-)"
)
# Words that make an older version history rather than a current claim when
# they precede it closely ("the previous 1.1.1 record", "since 1.1").
HISTORY_WORDS = re.compile(
    r"\b(?:previous|earlier|older|historical|prior|superseded|since|through|after|"
    r"before|from|until|than|introduced|added|replaced|preceding|followed)\b",
    re.IGNORECASE,
)
# Words that make a newer version a plan rather than a claim that it shipped.
UPCOMING_WORDS = re.compile(
    r"\b(?:upcoming|planned|plans?|unreleased|unpublished|development|developing|"
    r"not yet|not shipped|future|will|next|roadmap|candidate|target|targets|from|"
    r"starting|begins|until|scope|tracked|P0|work|preview|pending|proposed|once|"
    r"when|after|ledger|queue|branch|not|no|yet|zero|none|without)\b",
    re.IGNORECASE,
)
# A newer version aimed at ("for 1.4", "assigned to 1.3.2") is a plan.
TARGET_WORDS = re.compile(r"\b(?:for|to)\b", re.IGNORECASE)
# Measurements and other software that share the version shape.
NOT_A_RELEASE = re.compile(r"\s*(?:[KMGT]i?B|s\b|ms\b|%|seconds|minutes)")
NEGATED_CURRENT = re.compile(r"\bnot (?:\w+ ){0,2}current\b", re.IGNORECASE)
# Plans and Component specifications (intended behavior) may name later
# releases freely; their current-release claims are still checked.
PLAN_DOCUMENTS = ("ROADMAP.md", "components/**")
FENCE = re.compile(r"^\s*(```|~~~)")


def version_tuple(text):
    return tuple(int(part) for part in text.split("."))


def load_current():
    return json.loads(CURRENT.read_text())


def is_historical(relative, text):
    if any(fnmatch(relative, pattern) for pattern in HISTORICAL):
        current = load_current()
        if relative == current["notes"]:
            return False
        return True
    return any(line.strip() == MARKER for line in text.splitlines()[:10])


def current_state_documents(root=ROOT):
    seen = set()
    for pattern in CURRENT_STATE:
        for path in sorted(root.glob(pattern)):
            relative = path.relative_to(root).as_posix()
            if relative in seen or not path.is_file():
                continue
            seen.add(relative)
            text = path.read_text(errors="replace")
            if not is_historical(relative, text):
                yield relative, text


def lines_outside_history(text):
    """Yield (line number, line, in_code) for lines outside history passages."""
    history = False
    code = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.strip() == HISTORY_OPEN:
            history = True
            continue
        if line.strip() == HISTORY_CLOSE:
            history = False
            continue
        if FENCE.match(line):
            code = not code
            yield number, line, True
            continue
        if not history:
            yield number, line, code


def sentences(text):
    """Yield (first line number, sentence) for prose outside code and history."""
    paragraph = []
    for number, line, code in list(lines_outside_history(text)) + [(0, "", False)]:
        if code or not line.strip() or line.lstrip().startswith(("#", "|", "- ", "* ", "1. ")):
            if paragraph:
                yield from _split(paragraph)
                paragraph = []
            if not code and line.strip():
                # Headings, table rows and list items are their own units.
                paragraph = [(number, line.strip().lstrip("#|-* ").strip())]
            continue
        paragraph.append((number, line.strip()))
    if paragraph:
        yield from _split(paragraph)


def _split(paragraph):
    start = paragraph[0][0]
    joined = " ".join(line for _, line in paragraph)
    # Drop link targets and inline code so names such as tags and branches
    # are not mistaken for version claims.
    joined = re.sub(r"\]\([^)]*\)", "]", joined)
    joined = re.sub(r"`[^`]*`", "`code`", joined)
    for sentence in re.split(r"(?<=[.!?;])\s+(?=[A-Z*\[(])", joined):
        yield start, sentence


def versions_in(sentence):
    for match in VERSION.finditer(sentence):
        major, minor, patch = match.groups()
        version = (int(major), int(minor), int(patch or 0))
        yield match, version, patch is not None


def preceded_by(sentence, index, pattern, words=5):
    before = sentence[:index].split()[-words:]
    return bool(pattern.search(" ".join(before)))


def audit(root=ROOT, current=None):
    """Return a list of 'path:line: problem' strings."""
    current = current or load_current()
    version = version_tuple(current["version"])
    assets = current["assets"]
    current_digests = {entry[1].split(":", 1)[1] for entry in assets.values()}
    stale_digests = {}
    stale_sizes = {}
    for previous in current.get("previous_releases", []):
        name, size, digest = previous["image"]
        stale_digests[digest.split(":", 1)[1]] = previous["version"]
        stale_sizes[f"{size:,}"] = previous["version"]
        record = previous.get("record")
        if record and (root / record).is_file():
            for asset, (_, identity) in json.loads((root / record).read_text())["assets"].items():
                stale_digests[identity.split(":", 1)[1]] = previous["version"]
    image_names = {image["asset"] for image in current["images"]}
    problems = []
    for relative, text in current_state_documents(root):
        for number, line, _ in lines_outside_history(text):
            where = f"{relative}:{number}"
            for match in IMAGE.finditer(line):
                if match.group(1) != current["version"] and version_tuple(match.group(1)) < version:
                    problems.append(f"{where}: names older image {match.group(0)}")
            for digest in SHA.findall(line):
                if digest in stale_digests:
                    problems.append(f"{where}: carries the {stale_digests[digest]} checksum {digest}")
                elif any(name in line for name in image_names) and digest not in current_digests:
                    problems.append(f"{where}: checksum {digest} does not match the published assets")
            for size, old in stale_sizes.items():
                if size in line:
                    problems.append(f"{where}: carries the {old} image size {size}")
            for name in image_names:
                if name in line:
                    for size in re.findall(r"(\d{1,3}(?:,\d{3})+) bytes", line):
                        if size != f"{assets[name][0]:,}":
                            problems.append(f"{where}: says {name} is {size} bytes")
        for number, sentence in sentences(text):
            where = f"{relative}:{number}"
            tokens = list(versions_in(sentence))
            # A claim word refers to the version nearest to it, so "the current
            # 1.3.1, as did the 1.1.1 refresh" is not a claim about 1.1.1.
            claimed = set()
            if not NEGATED_CURRENT.search(sentence):
                for claim in CURRENT_CLAIM.finditer(sentence):
                    nearest = min(tokens, default=None, key=lambda token: min(
                        abs(token[0].start() - claim.end()), abs(claim.start() - token[0].end())))
                    if nearest:
                        claimed.add(nearest[0].start())
            for match, found, _ in tokens:
                claims_current = match.start() in claimed
                if found[0] == version[0] and found[1] == version[1] and found[2] in (0, version[2]):
                    continue
                if NOT_A_RELEASE.match(sentence, match.end()):
                    continue
                if found < version and claims_current and not preceded_by(sentence, match.start(), HISTORY_WORDS):
                    problems.append(f"{where}: presents {match.group(0)} as current: {sentence[:160]}")
                elif (found > version and found[0] == version[0] and found[1] <= version[1] + 3
                      and not any(fnmatch(relative, plan) for plan in PLAN_DOCUMENTS)
                      and not UPCOMING_WORDS.search(sentence)
                      and not preceded_by(sentence, match.start(), TARGET_WORDS, 2)):
                    problems.append(f"{where}: presents unreleased {match.group(0)} as available: {sentence[:160]}")
    return problems


class SourceOfTruth(unittest.TestCase):
    def setUp(self):
        self.current = load_current()

    def test_record_is_well_formed(self):
        current = self.current
        self.assertEqual(current["schema"], "daemonarchy/current-release@1")
        self.assertRegex(current["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(current["tag"], f"daemonarchy-{current['version']}")
        self.assertEqual(current["url"], f"https://github.com/jordanhubbard/daemonarchy/releases/tag/{current['tag']}")
        self.assertTrue((ROOT / current["notes"]).is_file(), current["notes"])
        self.assertTrue(current["images"], "every release publishes at least one image")
        for name, (size, digest) in current["assets"].items():
            self.assertTrue(name.startswith("daemonarchy-"), name)
            self.assertIn(current["version"], name)
            self.assertIsInstance(size, int)
            self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")
        types = set()
        for image in current["images"]:
            self.assertNotIn((image["type"], image["arch"]), types)
            types.add((image["type"], image["arch"]))
            self.assertIn(image["asset"], current["assets"])
            self.assertIn(image["checksum_asset"], current["assets"])
            self.assertRegex(image["asset"], IMAGE)
        for previous in current["previous_releases"]:
            self.assertLess(version_tuple(previous["version"]), version_tuple(current["version"]))

    def test_project_version_is_not_behind_the_release(self):
        project = json.loads((ROOT / "literate.project.json").read_text())["version"]
        self.assertGreaterEqual(version_tuple(project), version_tuple(self.current["version"]))

    def test_release_record_matches_when_present(self):
        record = ROOT / f"verification/release-{self.current['version']}.json"
        if not record.is_file():
            self.skipTest(f"{record.name} is not committed")
        assets = json.loads(record.read_text())["assets"]
        self.assertEqual({name: list(value) for name, value in assets.items()}, self.current["assets"])


class CurrentStateDocuments(unittest.TestCase):
    def setUp(self):
        self.current = load_current()
        self.readme = (ROOT / "README.md").read_text()

    def test_readme_download_section(self):
        current = self.current
        base = f"https://github.com/jordanhubbard/daemonarchy/releases/download/{current['tag']}/"
        self.assertIn(current["url"], self.readme)
        for image in current["images"]:
            size, digest = current["assets"][image["asset"]]
            self.assertIn(base + image["asset"], self.readme)
            self.assertIn(base + image["checksum_asset"], self.readme)
            self.assertIn(digest.split(":", 1)[1], self.readme)
            self.assertIn(f"{size:,} bytes", self.readme)
        self.assertIn(current["notes"], self.readme)

    def test_documentation_index_links_current_notes(self):
        index = (ROOT / "docs/README.md").read_text()
        self.assertIn(Path(self.current["notes"]).name, index)

    def test_release_procedure_names_the_source_of_truth(self):
        hacking = (ROOT / "HACKING.md").read_text()
        self.assertIn("release/current.json", hacking)
        self.assertIn("tests/docs-release-sync.py", hacking)

    def test_documents_agree_with_the_current_release(self):
        problems = audit()
        self.assertFalse(problems, "stale current-state documentation:\n" + "\n".join(problems))


class ShippedImageData(unittest.TestCase):
    def test_default_checkout_catalogue_is_the_current_feed(self):
        current = load_current()
        catalogue = json.loads(
            (ROOT / "overlay/usr/local/share/daemonarchy-installer/checkouts.json").read_text())
        self.assertEqual(
            catalogue["repository_url"],
            f"https://github.com/jordanhubbard/daemonarchy/releases/download/{current['checkout_feed']}",
        )


class GuardBehaviour(unittest.TestCase):
    """Fixtures proving that the guard catches regressions."""

    def setUp(self):
        import tempfile

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "docs").mkdir()
        self.current = load_current()

    def problems(self, text, name="docs/guide.md"):
        (self.root / name).write_text(text)
        return audit(self.root, self.current)

    def test_old_release_called_latest(self):
        self.assertTrue(self.problems("Daemonarchy 1.1.1 is the latest release.\n"))
        self.assertTrue(self.problems("The current product release is 1.1.1.\n"))

    def test_history_is_allowed(self):
        self.assertFalse(self.problems("The latest release replaced the previous 1.1.1 image.\n"))
        self.assertFalse(self.problems(
            f"{HISTORY_OPEN}\nThe current release was 1.1.1.\n{HISTORY_CLOSE}\n"))
        self.assertFalse(self.problems("The latest release is 1.1.1.\n", "docs/testing-1.1.1.md"))
        self.assertFalse(self.problems(f"{MARKER}\nThe latest release is 1.1.1.\n"))

    def test_old_image_and_checksum(self):
        self.assertTrue(self.problems("sudo dd if=daemonarchy-1.1.0-amd64.iso of=/dev/sdb\n"))
        self.assertTrue(self.problems(
            "Checksum: c1bc6e3a0d30e6806a324aa3abd76eb70f1593f9f22e7aab6d222491fc1eb956\n"))
        iso = self.current["images"][0]["asset"]
        self.assertTrue(self.problems(f"{iso}: {'0' * 64}\n"))
        self.assertTrue(self.problems(f"{iso}: 1,000 bytes\n"))

    def test_current_release_is_accepted(self):
        image = self.current["images"][0]["asset"]
        size, digest = self.current["assets"][image]
        self.assertFalse(self.problems(
            f"The latest release is {self.current['version']}: {image}, {size:,} bytes, "
            f"SHA-256 {digest.split(':', 1)[1]}.\n"))

    def test_unreleased_version_as_available(self):
        major, minor, _ = version_tuple(self.current["version"])
        self.assertTrue(self.problems(f"Daemonarchy {major}.{minor + 1}.0 adds a live desktop.\n"))
        self.assertFalse(self.problems(f"The upcoming {major}.{minor + 1}.0 adds a live desktop.\n"))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--list"]:
        for path, _ in current_state_documents():
            print(path)
        sys.exit(0)
    unittest.main()
