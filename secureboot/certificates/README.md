# Daemonarchy 1.1 public signing material

`daemonarchy-1.1.der` and `daemonarchy-1.1.pem` contain the same public
certificate. Its DER SHA-256 is:

```
111539a7fb7178cea65f3e2fc50ea00839d045324a4272ce190e4733a9c118dd
```

The certificate is valid from 2026-10-16 to 2036-10-13. Its private signing
key stays root-owned and owner-readable only on the protected signing host;
it is not an authoring-worker input or an image/package/repository file.
`daemonarchy-1.1-selftest.pem` is the public loader certificate-test fixture.
Its temporary private key was destroyed after issuance.

These files do not themselves qualify an image. Production firmware boot,
installation, rejection, update and recovery checks remain release gates.
Published previews use other boot paths; do not enroll a certificate merely
to try one of those images. Follow the final release's verified artifact and
[manual enrollment instructions](../../docs/secure-boot.md), appending only
to db and preserving existing OEM/Microsoft trust.
