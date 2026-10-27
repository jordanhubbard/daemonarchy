# Enterprise Wi-Fi

The installer and desktop support profiles for **PEAP/MSCHAPv2** and
**EAP-TLS**. Both require a trusted CA certificate and the DNS domain of the
authentication server. Obtain those values from the network administrator.
The interface does not offer an option to disable server verification.

In the installer, select a wireless network and choose **Enterprise (802.1X)**.
On the desktop, select an unfamiliar enterprise network in the Wi-Fi panel;
its setup form opens in a floating terminal. You can also run
`daemonarchy wifi enterprise 'Network name'`. Existing saved profiles connect
directly from the panel.

Provide the identity, CA certificate's PEM path and authentication-server
domain. PEAP additionally asks for a password and an optional anonymous
identity. EAP-TLS asks for the client certificate, matching private key, and
optional key password. Paths can contain spaces; do not add shell quotes in
the form. The desktop form accepts `~` in paths. TLS 1.0 and 1.1 are disabled.

Passwords pass to the privileged backend through standard input and the local
supplicant control socket. They are not included in process arguments.
Imported certificate material is copied into private directories; the key,
profile and supplicant configuration files use mode 0600. A failed profile
operation restores the previous saved configuration. The installer validates
the profile before disk writes and copies its material into the installed
system, so the source USB/files are not needed on the next boot.

The installer stages its active profile under `/tmp`, accessible
only to root. The installed system keeps its certificate material under
`/etc/wpa_supplicant/enterprise/` and its networks in
`/etc/wpa_supplicant.conf`. Forgetting a network removes it from the active
supplicant configuration; retained certificate files stay root-only.

## Validation boundary

Native FreeBSD tests cover PEM parsing and key matching, both configurations
with the real `wpa_supplicant` parser, private file permissions, installer
transfer, socket transport, and rollback after setting/authentication/save
failures. Form tests cover enterprise selection, hidden networks and failed
joins. These checks do not establish a successful association or an EAP
exchange against a real access point.

Introduced in 1.1, the implementation carries forward into 1.1.1 and the current 1.3.1; a source/package refresh does not supply new radio evidence. Native qualification still needs both EAP methods on a test network,
rejection of an untrusted server certificate and wrong server domain,
reconnection after reboot, and inspection of native logs for credential
disclosure. The operator approved publication with this limitation disclosed; configuration tests alone do not complete enterprise Wi-Fi qualification. See the earlier [1.1.1 record](testing-1.1.1.md); 1.3.1 adds no enterprise Wi-Fi radio evidence.
