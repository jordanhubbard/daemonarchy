# Login trace

Installed systems record how long the path from the login screen to a usable
desktop takes, so a slow first login can be measured instead of guessed at.

On the MSI the first frame appeared about ten seconds after the password was
entered. The logs show a gap of about three seconds before the user session's
`dbus-run-session` starts, then about seven seconds from the user's Hyprland
starting to its first monitor, but they have no sub-second timestamps and the
sequence cannot be replayed without logging the user out. The recorder gives that
timeline on every boot.

- **What:** the `daemonarchy_login_trace` rc service runs from boot until the
  first desktop is up (or 15 minutes), then exits. It polls ten times a second, so
  times have about 100 ms resolution.
- **Where:** one JSON line per boot is appended to
  `/var/log/daemonarchy-login-trace.jsonl` (schema `daemonarchy/login-trace@1`,
  the last 200 lines kept). It holds milestone names and times only: no command
  lines, paths, user names or credentials.
- **Milestones:** `boot`, `sddm`, `greeter_compositor`, `greeter_ready`, `login`
  (sddm-helper starts the user's session), `ck_launch_session`,
  `dbus_run_session`, `user_compositor`, `wayland_socket`, `monitor_ready`
  (Hyprland's IPC reports its first monitor, the first usable output),
  `quickshell`, `xwayland`.
- **Reading it:** `since_login_ms` gives each milestone's offset from the login, in
  order, so the long step is the largest difference between neighbours.
- **Off switch:** `daemonarchy_login_trace_enable="NO"` in `/etc/rc.conf`.

The installer copies the service in during the configuration phase. A stock
install therefore records its very first login, which is the case that is slow.
