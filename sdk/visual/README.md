# Daemonarchy visual SDK

Terminal graphics, effects, input actions and sound cues for Daemonarchy's
installer and for other programs. Standard library only; Python 3.9 or later.
The package is `daemonarchy_visual` (API 1.0). Full reference:
[docs/visual-sdk.md](../../docs/visual-sdk.md).

- Source: `overlay/usr/local/lib/daemonarchy-visual/daemonarchy_visual/`
  (shipped on the image as `/usr/local/lib/daemonarchy-visual`).
- Tests: `python3 -I tests/visual-sdk.py`.
- A host that is not the installer: [examples/sample_host.py](examples/sample_host.py).
- Install elsewhere: `pip install ./sdk/visual` from a checkout.
