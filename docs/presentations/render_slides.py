#!/usr/bin/env python3
"""Render a .pptx to PDF (LibreOffice) and one PNG per slide (pdftoppm).

Usage: render_slides.py deck.pptx outdir [dpi]
Used to look at the slides before committing; the PNGs are not tracked.
"""
import shutil
import subprocess
import sys
from pathlib import Path

deck, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
dpi = sys.argv[3] if len(sys.argv) > 3 else "55"
out.mkdir(parents=True, exist_ok=True)
soffice = shutil.which("soffice") or shutil.which("libreoffice")
subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out), str(deck)],
               check=True, stdout=subprocess.DEVNULL)
pdf = out / (deck.stem + ".pdf")
subprocess.run(["pdftoppm", "-r", dpi, "-png", str(pdf), str(out / "slide")], check=True)
print(pdf)
