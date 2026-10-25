# 1.1.1-to-1.3.1 full application package inventory

This is a 2026-10-25 pre-publication snapshot of all 510 packages in the
public 1.1.1 application feed against the selected 1.3.1 ports tree and
the currently staged FreeBSD 1600029 package catalogue. The per-package
[TSV](release-1.3.1-package-reuse-inventory.tsv) retains every classification,
old public SHA-256, source-tree identity and selected metadata comparison.
No package is admitted for reuse by this inventory alone.

| Classification | Packages |
| --- | ---: |
| `absent_from_selected_repository` | 10 |
| `package_version_changed` | 8 |
| `port_inputs_changed` | 1 |
| `present_but_uncatalogued` | 1 |
| `queued_changed_package` | 3 |
| `queued_same_package_needs_qualification` | 5 |
| `unchanged_port_and_dependency_metadata` | 320 |
| `unchanged_port_needs_dependency_abi_review` | 162 |

The 454 old filenames already present in the current repository have
different archive hashes from the public 1.1.1 assets. Another 56 old
filenames are absent. This is an archive-byte comparison, not proof that
their installed payloads differ. An older OSVERSION and changed build
metadata require explicit ABI and package-script qualification before
an old archive can be published in the new feed.

Chromium, CEF and OBS keep identical source trees and versions but are
still queued. LibreOffice changed from `26.8.0.3_2` to `26.8.1.1`,
and its source tree differs; its new native build is required. The active
browser and remaining package builds are preserved as fallback while
reuse qualification proceeds in an isolated FreeBSD test root.

## Largest old packages with unchanged port and dependency metadata

| Package | Old asset bytes | Old SHA-256 |
| --- | ---: | --- |
| `llvm22` | 291,844,941 | `sha256:f140f4437cc3b09f7ab945d48ff2979721c5d63bfb780a623d05dd71f44b73bf` |
| `llvm21` | 284,449,537 | `sha256:5d86fb858903fde4ce49777f4c004311c3fa381820054988b0577d434cbbc896` |
| `deno` | 88,571,067 | `sha256:2ae02371d5b8aeeb3cc2cb8dca3899d81d5bdd9c2b2eede116ef5b5894f85b6f` |
| `mono5.20` | 82,092,148 | `sha256:27bd0b3b0d7662fed0342fe1b75d4058e36679382d831b6186280d8554ed829f` |
| `linux_base-rl9` | 60,220,146 | `sha256:d96b7440228a0605f97e5fe1c21bcc1ff9d81dc886796813ef8e70f7da1ef9b6` |
| `python312` | 40,694,461 | `sha256:56bd5adf30f34e9cd07a0367d4a33a14a49b0889cb19681cec6ad75e0811d88d` |
| `mise` | 32,475,301 | `sha256:20e4b153f55353b13ce9fda9180a7d97c7bd01f37906ea55cf098efaf034559e` |
| `zig` | 28,451,296 | `sha256:718cc93ad4f772991328dbb3201c4c87bf14824127e180072707a809ea6ee5be` |
| `yaru-icon-theme` | 26,632,727 | `sha256:2b5f8ce40e6b9ffb7f7661b41a8554b753b90b3992e4fa4c6df205159d36dee5` |
| `gdal` | 22,747,136 | `sha256:8ab84047aa57e35af58cce7315be0a80155ba1f529842811b8076157f5f6f596` |
| `py312-numpy` | 20,366,383 | `sha256:23e835d49143fa01d9fe03acb441d052b0ac4d4e4aa174b6834e85dd75f288ee` |
| `spidermonkey128` | 15,016,545 | `sha256:5977e64496556635d81e4a4af216317988b7a0c372df480e02f0808db7612535` |
| `cmake-core` | 14,742,545 | `sha256:ac5799d704515061cfce892c7535a6ce8236d3346fdd36f15c4d93d9a6e2906a` |
| `tex-formats` | 14,335,840 | `sha256:f31e27fca1b0a8e2bab1a8b195fcc7151860ed96b9da1d327e608619b4084c48` |
| `linux-rl9-python39` | 14,264,091 | `sha256:e8bb468145739264d08cf9fe5b2d47e16775ea0a17d317df344ae3106d8cf9e0` |
| `glib` | 11,232,414 | `sha256:a165ccda8757da0eedd740f9db533da3b91252c53787dfdd59d697ef54ea2067` |
| `cliamp` | 10,441,666 | `sha256:04248aeba9131d6f9e9430faaebfc464fabf62642064d0c79b76413389950b75` |
| `git` | 9,848,776 | `sha256:115fae9b82c528ea0e7c1400152115c1d730bc0cf7d2fdf108e44a9011ec5580` |
| `doxygen` | 8,767,660 | `sha256:7a6db7ec25de0af94ec264d847657029045050e3d5e892c46f1e45e3dd0ae044` |
| `py312-Babel` | 7,083,865 | `sha256:ef6b2e4095f76123c2c8da6c8568d6c5dd1656b92641bfdc506bd7d30ecfdfd7` |
