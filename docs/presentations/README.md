# Daemonarchy presentations

Two slide decks for the 1.5.x line, each built from a Markdown specification so the content
is reviewable and reproducible. They describe the published 1.5.0 release as documented in
the repository and mark 1.5.1 items as plans.

| Deck | Audience | Narrative | Slide source | Built |
| --- | --- | --- | --- | --- |
| Daemonarchy for users and decision makers | Prospective users | [narrative](daemonarchy-marketing/narrative-specification.md) | [slides](daemonarchy-marketing/deck-specification.md) | [pptx](daemonarchy-marketing/daemonarchy-marketing.pptx), [pdf](daemonarchy-marketing/daemonarchy-marketing.pdf) |
| Hacking on Daemonarchy | Developers and contributors | [narrative](daemonarchy-engineering/narrative-specification.md) | [slides](daemonarchy-engineering/deck-specification.md) | [pptx](daemonarchy-engineering/daemonarchy-engineering.pptx), [pdf](daemonarchy-engineering/daemonarchy-engineering.pdf) |

Every slide has a `source:` line naming the repository document its claims come from, and the
narrative specifications carry a claim ledger. Screenshots come from `docs/images/`.

## Rebuild

```sh
python3 -m venv /tmp/deckvenv && /tmp/deckvenv/bin/pip install -r requirements.txt
/tmp/deckvenv/bin/python build_deck.py              # both decks
/tmp/deckvenv/bin/python build_deck.py engineering  # one deck
/tmp/deckvenv/bin/python build_deck.py --render     # also PDF and PNG previews
```

Tools: Python 3.10 or later with `python-pptx` and `Pillow` (see [`requirements.txt`](requirements.txt)). Rendering
needs LibreOffice (`soffice`) and `pdftoppm` (poppler). Fonts are Arial and Courier New in the
file; the metrics are checked against Liberation Sans and Liberation Mono. No network and no
model calls are used. [`build_deck.py`](build_deck.py) drives the build, [`deckkit.py`](deckkit.py) holds the layout code and documents the specification
dialect; [`render_slides.py`](render_slides.py) rasterises a deck so slides can be inspected before committing.
