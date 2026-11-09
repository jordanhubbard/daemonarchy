# ARM platform register

The [1.6 register](roadmap/arm-platforms.json) retains every named target in the
[release plan](roadmap/release-1.6.0.md), including unavailable hardware and
families whose exact reference model still needs selection. It is an ARM-001
discovery inventory, not a support matrix or an execution receipt.

```sh
python3 scripts/arm-platform-register.py
python3 tests/arm-platform-register.py -v
```

The command checks required scope, unique profile IDs, work ownership, hardware
allocation, identity fields, source references and the complete feature matrix.
Its JSON output lists unresolved identity fields and counts unknown, blocked,
failed and passed states separately. Exit zero means the inventory is internally
consistent; it does not mean any target passed qualification.

Each scope row needs an individual test owner and an explicit hardware allocation.
Unknown board revisions, RAM, firmware, boot chains, ABIs and storage paths use
JSON `null`. Model descriptions containing “pending” retain an unresolved selection;
they do not enroll an exact machine. Source links lead to the pinned research and
release requirements. They do not establish a selected release source revision.

Add a row for each concrete board/carrier/RAM/firmware/boot-mode/ABI/media variant
before testing it. Keep the original scope row visible until all required variants
are resolved. Record discovery gaps and implementation dependencies in
`discovery_needed`; record failures and blockers with their actual evidence in the
feature note. Keep private worker addresses, serial numbers and raw traces out of
this public register. A historical reference machine has no assumed release test
allocation. In particular, Linux on DGX, Apple-hosted VMs, Pi simulator controls
and the Spark four-core experiment cannot qualify a final distribution row.

The initial register has no admitted final-image results. The validator refuses
`passed` until a reviewed receipt admission contract binds results to the exact
model/revision/firmware/ABI/media, image/feed and source identities. That contract
must cover all final validation requirements in the release plan, including
physical versus VM evidence. Inventory checks cannot supply it. Preserve unknown
results until actual evidence establishes failure, a specific blocker, or an
admissible result; no family-wide support inference is permitted.

Removing or narrowing a required target requires the operator scope decision
specified by the release plan, followed by review of both the inventory and the
required IDs in the checker. Additions do not remove prior obligations. ARM-001
remains open for concrete enrollment, current immutable upstream evidence and
final-image evidence links; ARM-006 remains open for distribution qualification.
