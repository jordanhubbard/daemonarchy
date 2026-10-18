# Bluetooth audio development checks

Historical 1.1 development/candidate evidence. Revisions, checksums and results
below apply to the named artifact and date; they do not qualify the new
[1.1.1 source/package set](testing-1.1.1.md). Follow that record for current
preparation and publication status.

Checked 2026-10-16 against the October 12 snapshot, source
`3ceb5f150bc121f5e6a3e0cc8b289279338405a1`, in the installed QEMU graphics
fixture. This is audio plumbing evidence, not a successful Bluetooth exchange.

The compatibility-layer implementation is
`omarchy-freebsd` commit `8f8904db1be3eafcdbab9406cbfa9ae097f1ee7d`.
It detects the A2DP Audio Sink service, starts FreeBSD's base `virtual_oss`
with the native Bluetooth backend, and lets the desktop account create its
own PipeWire OSS adapter. A successful Connect action selects that output.
Disconnect, forget and power-off remove it. Login restores the selected
backend without overriding another saved default output. HID-only devices
retain their existing path; failed HCI connections are not reported as success.

The intended profile is stereo A2DP/SBC playback, one Bluetooth output at a
time. HFP/microphone capture, AAC and simultaneous Bluetooth outputs are not
implemented or qualified.

The stock PipeWire OSS monitor only enumerates kernel `pcm` devices; merely
registering a virtual OSS device did not expose an output in the desktop.
Creating a native `freebsd-oss.sink` adapter with the virtual device's path
made it visible through the regular output selector.

## Checks

- Portable policy checks passed: HID isolation, A2DP service detection,
  HCI/startup failures, repeated routing without duplicate nodes, saved-output
  preservation and removal of only the matching output.
- Native `virtual_oss_bluetooth-1600027` installed successfully in the guest.
- The native bridge test created a real virtual OSS character device and a
  user-owned PipeWire sink, selected it as the default, wrote PCM through it,
  reused the adapter on a subsequent route, and removed the node, character
  device and saved state on stop. Its backend log had mode 0600.
- This test substitutes `/dev/null` for the Bluetooth transport. It exercises
  the actual OSS/PipeWire functions, but does not exercise Bluetooth pairing,
  authentication, codec negotiation, radio playback or a headset reconnect.
- The existing compatibility-layer Python suite passed 28 tests with five
  native/root-only checks skipped on macOS, using the real pinned upstream
  router/menu/bindings fixtures. Those skips are not new native evidence.

Reproduce with `tests/bluetooth-audio.sh` and, in an active FreeBSD desktop
session with sudo available, `tests/bluetooth-audio-native.sh` in the
compatibility repository. Do not describe the null transport test as headset
playback. Real headset/speaker playback and volume, disconnection/reconnection,
reboot restoration, output switching, and HID regression checks remain open.
