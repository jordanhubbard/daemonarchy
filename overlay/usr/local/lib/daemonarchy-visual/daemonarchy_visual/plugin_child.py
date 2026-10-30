#!/usr/bin/env python3
"""The process a plugin runs in. Started only by daemonarchy_visual.plugin; not a public entry point.

  python3 -I plugin_child.py PLUGIN_DIR ENTRY CONFIG_JSON

It lowers its own limits and privileges, loads the plugin's entry file, then answers one JSON
line per tick from the host with one JSON line holding a frame (rows of styled runs), the audio
cues requested, and whether the scene is done. It reads no files of the host's, holds none of the
installer's state, and cannot write to the terminal: its stdout is the protocol and the plugin's
own stdout is discarded. The plugin is trusted, hash-verified content; this process is the
safety net for its bugs (a crash, a hang, a runaway loop), not a sandbox for hostile code.
"""

import importlib.util
import json
import os
import sys

NOBODY = 65534


def harden(limits):
    """Bound memory, CPU, files and forks, then drop root. Failing to drop root is fatal."""
    try:
        import resource
        mem = int(limits.get("memory_mb", 64)) * 1024 * 1024
        for name, value in (("RLIMIT_AS", mem), ("RLIMIT_CPU", int(limits.get("cpu_seconds", 900))),
                            ("RLIMIT_NOFILE", 32), ("RLIMIT_FSIZE", 0), ("RLIMIT_CORE", 0)):
            if hasattr(resource, name):
                try:
                    resource.setrlimit(getattr(resource, name), (value, value))
                except (ValueError, OSError):
                    pass
        if hasattr(resource, "RLIMIT_NPROC"):
            try:
                resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
            except (ValueError, OSError):
                pass
    except ImportError:
        pass
    os.chdir("/")
    if os.geteuid() == 0:
        try:
            os.setgroups([])
            os.setgid(NOBODY)
            os.setuid(NOBODY)
        except OSError:
            os._exit(126)  # never run a plugin as root
        if os.geteuid() == 0:
            os._exit(126)


def encode(canvas):
    """Rows of (text, style id) runs and the style table; small enough to send every frame."""
    table, index, rows = [], {}, []
    for chars, styles in zip(canvas.chars, canvas.styles):
        runs, current, text = [], object(), []
        for char, style in zip(chars, styles):
            if style != current:
                if text:
                    runs.append(["".join(text), index[current]])
                    text = []
                current = style
                if style not in index:
                    index[style] = len(table)
                    fg, bg, bold = style if style else (None, None, False)
                    table.append([list(fg) if fg else None, list(bg) if bg else None, bool(bold)])
            text.append(char)
        if text:
            runs.append(["".join(text), index[current]])
        rows.append(runs)
    return rows, table


def main(argv):
    plugin_dir, entry, config = argv[1], argv[2], json.loads(argv[3])
    sdk_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, sdk_root)
    # Keep the protocol on a private descriptor; whatever the plugin prints goes nowhere.
    protocol = os.fdopen(os.dup(1), "w", buffering=1)
    sys.stdout = open(os.devnull, "w")
    harden(config.get("limits", {}))

    import daemonarchy_visual as sdk
    from daemonarchy_visual.audio import Audio, CUES
    from daemonarchy_visual.canvas import Canvas
    from daemonarchy_visual.scene import Context

    class Sink(Audio):
        def __init__(self):
            self.cues = []

        def _play(self, name, params):
            if "audio" in config["capabilities"] and len(self.cues) < 16:
                self.cues.append(name)
            return True

    path = os.path.join(plugin_dir, entry)
    spec = importlib.util.spec_from_file_location("daemonarchy_plugin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    caps = sdk.Capabilities(depth=config["depth"], unicode=config["unicode"], reduced=config["reduced"],
                            plain=False, console=config["console"], width=config["width"],
                            height=config["height"], audio="audio" in config["capabilities"])
    sink = Sink()
    ctx = Context(caps, sink)
    scene = module.create(sdk.API_VERSION)
    scene.start(ctx)
    wants_input = "input" in config["capabilities"]
    for line in sys.stdin:
        try:
            tick = json.loads(line)
            caps.width, caps.height = int(tick["w"]), int(tick["h"])
            actions = [a for a in tick.get("a", []) if a in sdk.ACTIONS] if wants_input else []
            scene.update(min(0.1, max(0.0, float(tick["t"]))), ctx, actions)
            canvas = Canvas(caps.width, caps.height)
            scene.draw(canvas, ctx)
            rows, table = encode(canvas)
            reply = {"f": rows, "s": table, "c": sink.cues, "d": bool(scene.done), "r": scene.result}
            sink.cues = []
        except Exception as error:  # noqa: BLE001 - report the plugin's failure, then stop.
            reply = {"e": type(error).__name__}
            protocol.write(json.dumps(reply) + "\n")
            return 1
        protocol.write(json.dumps(reply, separators=(",", ":")) + "\n")
        if reply["d"]:
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
