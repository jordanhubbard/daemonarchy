# 1.4 network-debug native rerun, 2026-10-26

This rerun covers the three DEBUG-003 bhyve cases left open by the
[earlier October 26 native run](roadmap/1.4-coverage-ledger.md#october-26-native-debug-003-run):
`d1-loader-ops` with the default `net0:/kernel` TFTP kernel,
`d3-handoff-vtnet` and the two-NIC `d3-early-em`. All three passed on
their first attempt. It is development evidence for the VM backends only.
It is not physical-NIC, MSI or release qualification.

## Worker and isolation

The cases ran on daemon.local, the FreeBSD 16.0-CURRENT amd64 build and
test worker, after its LIVE-001 run had finished. `vmm` and `nmdm` were
already loaded. The source checkout, object directory, runner tools and
evidence each went into new directories named for this rerun. No retained
LIVE-001 evidence, jail, tree or repository was modified or removed.

Each case ran alone under the runner's bounds: `timeout -k` around bhyve,
a `bhyvectl --destroy` watchdog, the case's own destroy once its
observation was complete, and an outer `timeout -k 30 1500` around the
runner. Admission required no other bhyve guest, at least 1.5 GiB of free
plus inactive memory, a new evidence directory and matching SHA-256
identities. After every case `/dev/vmm` was empty, no `bhyve` process
remained and only the host's own interfaces were left. The case images
are plain files made by `makefs` and `mkimg`, so no md device is used,
and none was present afterwards.

## Inputs

- Source `origin/daemonarchy` at `fd259a1787ab` (tree
  `d33592c2e13039ec73250f760b6729a21fe0cde4`): the merge of source PR #33,
  with TFTP preload into firmware pages, the 16 KiB mountroot console
  pre-poll ring and the `netdebug.early.*` em overrides. The checkout was
  clean.
- Built with the same commands as the earlier run, in a new object
  directory. `buildkernel` and the `stand` build both exited 0.
- `DAEMONARCHY_DIAGNOSTIC` kernel
  `806fdd419e5bacf76773449b12f5684d3641f1eb5ec9d6051257476873ffa2b2`.
- Symbols `75a561d5acaea487851d93469831b729ff75c1783b6625af3c1983a5100b975f`.
- EFI loader `68ccda4cb862765c54aaecf0b6e15fff72ca566e33c3ae1238961c8a7a5b3f73`.
- Loader Lua tree `1f7139046776500bbe84c97ee61890c087e4617a6eb9ba35497cf0fc93a2fbec`
  (unchanged from the earlier run).
- Runner tools tree from the same commit,
  `a33c12647dc210448e050eeb2ebc962bf45e14d9e671fd817b49065816021c82`.
  Each case records these identities in its `result.json`.

## Results

| Case | Result | Evidence manifest SHA-256 |
|---|---|---|
| `d1-loader-ops` (`net0:/kernel`) | pass, all 10 criteria | `91f5f5654a59b7583314d2fe48865fef98eeb329e9de0d71099d230c36554f93` |
| `d3-handoff-vtnet` | pass, all 7 criteria | `338d4947582999980b5e765a849ec04b2cfd15d926d1de8f56fd84c86a4decf4` |
| `d3-early-em` (two NICs) | pass, all 5 criteria | `6680d913fb0aa5ba20b209c2b1404250abb6fc02681d105fa362ddaac0ddd4d6` |

The manifest is each case's `evidence-sha256.txt`, which lists the SHA-256
of every file in the case directory. Raw captures, serial logs and disk
images stay in the isolated worker evidence root.

**`d1-loader-ops`.** The real loader set, unset and showed variables. It
downloaded the 31,540,560-byte kernel over TFTP and loaded it as
`net0:/kernel`. The TFTP server logged three `/kernel` requests: two
abandoned within 30 ms of the first, at blocks 1 and 23, then one full
transfer completing in 22.53 s. No request followed the full transfer, and
the ELF load printed its `text=` and `data=` segments from the preloaded
copy. The earlier run stalled on re-downloads during the ELF load; this
one had none. A staged Lua file was downloaded and run by `include`,
`netdebug stop` made a new controller fail to pair, and a serial
`netdebug auto` restart paired again with `daemonarchy.d1=set-ok` still
set. The guest was destroyed at the loader prompt, and bhyve exited on the
known `emulate_inout` assertion (status -6) described in source
`tools/daemonarchy/bhyve-emulate-inout-note.md`.

**`d3-handoff-vtnet`.** The early transport was admitted on vtnet at
`0:0:3:0`, released, and native `vtnet0` attached after the release. The
mountroot console reheralded in the same controller session, and its own
`kernel-rootconf` stage marker reached the controller. The earlier run
lost that marker to the old 512-byte pre-poll buffer. Root-mount input sent over the
network produced `Trying to mount root from ufs:/dev/vtbd0p2` on the
serial console, and the controller finished normally.

**`d3-early-em`.** The guest had virtio-net at slot 3 for the loader
console and e1000 at slot 4 on its own tap and subnet. The loader paired
over virtio-net. The kernel's early transport then reported
`backend=em pci=0:0:4:0` and claimed the e1000 function as `earlynet0`.
The em tap capture shows the guest's ARP from `192.0.3.2` for the
controller at `192.0.3.1`, then debugnet traffic between them (both are
documentation addresses on the case's private tap). The deliberate
pre-driver panic arrived over that transport, DDB `show pcpu` was entered
remotely and answered (`curthread` returned), the panic text was recorded
as the last stage, and `em0` never attached. Native `vtnet0` did attach
before the panic, as expected, because it is not the early NIC in this
design.

## Observations

- The em-tap `tcpdump` reported 82 packets matched but wrote only 15,
  because the runner stops capture immediately after the guest is
  destroyed. The packets it wrote are enough to identify the em source
  address and ports, and the case criteria come from the controller
  capture rather than the pcap. A future runner change could pass
  `--immediate-mode` or wait for capture to drain before stopping it.
- The `d1` teardown again hit the bhyve `emulate_inout` assertion. It
  affected only the destroyed guest.

## Scope still open

These are VM results. They do not cover physical NICs, the MSI built-in
NIC, anything before `SI_SUB_KMEM`, downloaded module selection or release
acceptance. The cases that passed in the earlier run were not repeated on
this build.
