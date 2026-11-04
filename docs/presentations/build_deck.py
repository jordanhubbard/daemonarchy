#!/usr/bin/env python3
"""Build the Daemonarchy decks from their specifications.

Usage:
    python3 build_deck.py                 build both decks
    python3 build_deck.py marketing       or: engineering
    python3 build_deck.py --render        also render PDF + PNG previews into
                                          $DECK_RENDER_DIR (default /tmp)

Outputs, next to each deck-specification.md:
    daemonarchy-marketing/daemonarchy-marketing.pptx
    daemonarchy-engineering/daemonarchy-engineering.pptx
Requires python-pptx and Pillow (requirements.txt); --render also needs
LibreOffice (soffice) and pdftoppm (poppler).
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import deckkit  # noqa: E402

DECKS = {"marketing": "daemonarchy-marketing", "engineering": "daemonarchy-engineering"}


def main(argv):
    render = "--render" in argv
    names = [a for a in argv if not a.startswith("--")] or list(DECKS)
    for name in names:
        d = HERE / DECKS[name]
        out = d / f"{DECKS[name]}.pptx"
        n = deckkit.build(d / "deck-specification.md", out)
        print(f"{name}: {n} slides -> {out}")
        if render:
            rd = Path(os.environ.get("DECK_RENDER_DIR", "/tmp")) / DECKS[name]
            subprocess.run([sys.executable, str(HERE / "render_slides.py"), str(out), str(rd)], check=True)
            pdf = rd / out.with_suffix(".pdf").name
            (d / pdf.name).write_bytes(pdf.read_bytes())
            print(f"  previews in {rd}")


if __name__ == "__main__":
    main(sys.argv[1:])
