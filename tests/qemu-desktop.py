#!/usr/bin/env python3
"""POST_INSTALL_CHECK for the disposable QEMU/VirGL guest, with real UI input."""
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import time
from urllib.parse import quote

work, port = Path(sys.argv[1]).resolve(), str(int(sys.argv[2]))
environment = dict(os.environ, SSH_ASKPASS=str(work / "askpass.sh"),
                   SSH_ASKPASS_REQUIRE="force", DISPLAY=":0")


def guest(command):
    return subprocess.check_output([
        "ssh", "-p", port, "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR", "-o", "PreferredAuthentications=password,keyboard-interactive",
        "-o", "PubkeyAuthentication=no", "-o", "ConnectTimeout=10", "tester@127.0.0.1", command,
    ], env=environment, text=True, stderr=subprocess.DEVNULL).strip()


def wait_for(action, description, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = action()
            if result:
                return result
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pass
        time.sleep(2)
    raise RuntimeError("Timed out waiting for " + description)


sock = socket.socket(socket.AF_UNIX)
sock.settimeout(30)
# QEMU binds a short relative name; long retained-evidence paths can exceed
# sockaddr_un.sun_path if the client uses their absolute spelling.
os.chdir(work)
sock.connect("boot.log.qmp.sock")
stream = sock.makefile("rwb", buffering=0)
stream.readline()
sequence = 0


def qmp(command, arguments=None):
    global sequence
    sequence += 1
    request = dict(execute=command, id=sequence)
    if arguments:
        request["arguments"] = arguments
    stream.write((json.dumps(request) + "\n").encode())
    while True:
        reply = json.loads(stream.readline())
        if reply.get("id") != sequence:
            continue
        if "error" in reply:
            raise RuntimeError(reply["error"])
        return reply.get("return")


def key(name):
    qmp("human-monitor-command", {"command-line": "sendkey " + name})
    time.sleep(0.15)


def pointer(x, y, click=False):
    events = [dict(type="abs", data=dict(axis="x", value=round(x * 32767 / 1279))),
              dict(type="abs", data=dict(axis="y", value=round(y * 32767 / 799)))]
    if click:
        events.append(dict(type="btn", data=dict(button="left", down=True)))
    qmp("input-send-event", dict(events=events))
    if click:
        qmp("input-send-event", dict(events=[dict(type="btn", data=dict(button="left", down=False))]))


def screenshot(name):
    # EGL headless can expose only a GL scanout, without the CPU surface
    # required by QMP screendump. Capture the compositor's actual output.
    owner = "tester" if guest("pgrep -u tester Hyprland || true") else "sddm"
    capture = ("export XDG_RUNTIME_DIR=/var/run/xdg/" + owner + "; "
               "export WAYLAND_DISPLAY=$(basename $(find $XDG_RUNTIME_DIR -maxdepth 1 "
               "-type s -name 'wayland-*' | head -1)); grim -")
    command = "sh -c " + shlex.quote(capture)
    if owner == "sddm":
        command = "printf '%s\\n' daemonarchy | sudo -S -u sddm " + command
    data = subprocess.check_output([
        "ssh", "-p", port, "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR", "-o", "PreferredAuthentications=password,keyboard-interactive",
        "-o", "PubkeyAuthentication=no", "tester@127.0.0.1", command,
    ], env=environment, stderr=subprocess.DEVNULL)
    assert data.startswith(b"\x89PNG\r\n\x1a\n"), "compositor did not return a PNG"
    (work / name).write_bytes(data)


def hypr(command):
    return guest("env XDG_RUNTIME_DIR=/var/run/xdg/tester hyprctl -i 0 " + command)


def complete_theme_authorization():
    # Only authorize this known first-run operation in the disposable guest.
    # Its Quickshell prompt is a layer surface, absent from activewindow.
    query = "pgrep -f '^pkexec /usr/local/bin/omarchy-theme-set-browser-policy [0-9a-fA-F]{6}$' || true"
    if guest(query):
        if os.environ.get("ALLOW_LEGACY_THEME_AUTH") != "true":
            screenshot("desktop-unexpected-theme-authorization.png")
            raise RuntimeError("FreeBSD theme setup unexpectedly requested administrator authorization")
        time.sleep(1)
        screenshot("desktop-theme-authorization.png")
        for character in "daemonarchy":
            key(character)
        key("ret")
        wait_for(lambda: not guest(query), "first-run theme authorization", timeout=20)


qmp("qmp_capabilities")
autologin = os.environ.get("ENCRYPT_INSTALLATION") == "true"
if not autologin and not guest("pgrep -u tester Hyprland || true"):
    wait_for(lambda: guest("pgrep -u sddm Hyprland"), "SDDM's Hyprland greeter")
    screenshot("desktop-greeter.png")
    pointer(664, 473, click=True)
    key("ctrl-a")
    for character in "daemonarchy":
        key(character)
    key("ret")
wait_for(lambda: guest("pgrep -u tester Hyprland"), "Hyprland user session")
wait_for(lambda: guest("pgrep -u tester quickshell"), "desktop panel")
monitors = json.loads(hypr("-j monitors"))
assert monitors and monitors[0]["width"] == 1280 and monitors[0]["height"] == 800, monitors
errors = json.loads(hypr("-j configerrors"))
assert not any(error.strip() for error in errors), errors
time.sleep(3)
complete_theme_authorization()
screenshot("desktop-ready.png")
before = json.loads(hypr("-j clients"))
addresses = {client["address"] for client in before}
key("meta_l-ret")
def terminal_focused():
    window = json.loads(hypr("-j activewindow"))
    return "foot" in window.get("class", "").lower() and window.get("address") not in addresses


wait_for(terminal_focused, "terminal opened and focused by keyboard")
# Let the compositor finish mapping/focus cursor warps before testing the tablet.
time.sleep(1)
# QEMU suppresses an unchanged absolute sample on repeated callbacks, even if
# the compositor has since warped its own cursor while focusing a new window.
pointer(0, 0)
time.sleep(0.2)
pointer(400, 300)
time.sleep(1)
position = json.loads(hypr("-j cursorpos"))
assert abs(position["x"] - 400) <= 3 and abs(position["y"] - 300) <= 3, position
screenshot("desktop-input.png")
page = "data:text/html," + quote(
    "<title>Daemonarchy browser check</title><h1>Daemonarchy browser check</h1>")
browser_command = "omarchy-launch-browser " + shlex.quote(page)
hypr("dispatch " + shlex.quote('hl.dsp.exec_cmd(' + json.dumps(browser_command) + ')'))
def browser_ready():
    complete_theme_authorization()
    window = json.loads(hypr("-j activewindow"))
    if window.get("title") == "Chromium Additional Terms of Service":
        # The upstream first-run dialog needs room for its Accept button.
        key("meta_l-f")
        screenshot("desktop-browser-first-run.png")
        key("ret")
        return False
    return "Daemonarchy browser check" in window.get("title", "")


wait_for(browser_ready,
         "native browser rendering the requested page", timeout=120)
screenshot("desktop-browser.png")
hypr("dispatch " + shlex.quote('hl.dsp.exec_cmd("octopkg")'))
def packages_ready():
    window = json.loads(hypr("-j activewindow"))
    if window.get("class") == "qt-sudo":
        screenshot("desktop-packages-authentication.png")
        for character in "daemonarchy":
            key(character)
        key("ret")
        return False
    return "octopkg" in window.get("class", "").lower()


wait_for(packages_ready,
         "native graphical package manager", timeout=60)
screenshot("desktop-packages.png")
(work / "desktop-evidence.json").write_text(json.dumps(dict(
    monitors=monitors, pointer=position, clients=json.loads(hypr("-j clients")),
    packages=guest("pkg query '%n %v' daemonarchy omarchy chromium octopkg"),
    kernel=guest("uname -v"),
    checks=["encrypted-install autologin" if autologin else "SDDM password login",
            "Hyprland monitor", "no configuration errors",
            "desktop panel", "terminal opened by keyboard", "absolute pointer input",
            "native browser launcher and requested data page", "native package manager UI"]), indent=2) + "\n")
print("PASS: graphical login, input, native browser and package manager; screenshots retained", flush=True)
