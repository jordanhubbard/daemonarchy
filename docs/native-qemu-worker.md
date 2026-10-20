# Disposable QEMU worker ownership

`native/qemu-worker.py` supervises one operator-started disposable worker. It owns
the QEMU child, enforces a monotonic lifetime and answers read-only allocation
inspection requests. It does not implement automatic Literate AI allocation or
prove a source-built SDK, native lifecycle receipt or release acceptance.

The controller tests use a fake QMP process. Actual QEMU, FreeBSD boot, SSH relay
and installed lifecycle qualification require separate native evidence.

The [first native checkpoint](../verification/native-qemu-worker-development.json)
boots FreeBSD 16.0-CURRENT through the versioned supervisor. Three fresh root-relay
inspections identify the same owned VM; replayed, wrong-plan and control-field
requests refuse while the worker stays live. The 12 controller checks also pass.
This native check uses an operator fixture context. A later actual interruption
check shuts the guest down through the supervisor: buffers sync, QEMU exits zero,
both owned processes terminate and the inspection socket is removed. The input
disk is preserved before preparing a larger cold copy. Automatic expiry,
installed framework integration and the original-source lifecycle remain open.

## Prepare a private case

Use a fresh short absolute directory owned by the operator with mode 0700.
Preserve completed cases. The supervisor refuses existing session records, logs
and sockets. Case paths cannot contain QEMU option delimiters or exceed the Unix
socket path budget.

Place `guest.qcow2` and `cidata.iso` in this directory. Both must be owned,
single-link regular files. The disk must be a standalone qcow2 image without
backing files. If carrying forward an earlier disposable worker, first confirm
its supervisor is terminal and its guest has shut down; convert the stopped
image into a new standalone copy. Never copy a live image. Keep the input image,
conversion log and identities with the case. The supervisor records hashes of
the complete initial disk, seed, QEMU executable, image inspection tool and its
own source before starting the worker.

Create `worker.json` with mode 0600:

```json
{
  "schema": "daemonarchy/qemu-worker-config@1",
  "qemu_binary": "/absolute/path/to/qemu-system-x86_64",
  "ssh_port": 22230,
  "maximum_runtime_seconds": 21600,
  "workspace_prefix": "/usr/daemonarchy/retained-native",
  "memory_mib": 2048,
  "cpus": 1,
  "accelerator": "tcg,thread=multi",
  "cpu": "Westmere"
}
```

The matching `qemu-img` must be beside the resolved QEMU executable. Resources
and acceleration are operator selections; this example makes no performance
claim. The guest seed must provide the approved SSH identity and network setup.
Create the selected private workspace inside the guest before retained execution.

Start the supervisor as a finite foreground job whose process handle and logs
the controller retains:

```sh
python3 native/qemu-worker.py --config "$DAEMONARCHY_VM_CASE/worker.json"
```

The only network listener is guest SSH forwarded to the selected loopback port.
`started.json`, `inspections.jsonl`, `terminal.json`, `console.log` and `qemu.log`
remain in the private case. The inspector socket is `inspection.sock`; QMP stays
private at `qmp.sock`. Guest reboot exits this allocation rather than silently
replacing its execution context.

## Bind a reviewed retained plan

After boot and toolchain alignment, review the exact retained plan and copy its
worker, plan and secondary-policy SHA-256 identities into a private mode-0600
`inspection-policy.json` beside `worker.json`. Its schema is
`daemonarchy/qemu-worker-inspection-policy@1`, with exactly `worker_identity`,
`plan_identity` and `policy_identity` in addition to `schema`. Policy is selected
by the operator; a wire request cannot establish or change this binding.

The supervisor checks its actual owned child, live QMP running state and attached
disk/seed on each successful request. Requests bind a fresh challenge to the
reviewed context. Replays, unknown fields and mismatched contexts refuse. Actual
allocation/input drift, insufficient lifetime and QMP failure revoke inspection.
The complete protocol uses the framework's existing allocation-inspection
request/response schemas. No request can allocate, stop, reboot or execute a
supplied command.

Forward only the inspection socket through the approved SSH connection:

```sh
ssh -N -o ExitOnForwardFailure=yes -o StreamLocalBindMask=0177 \
  -R "/var/run/litai-inspection.sock:$DAEMONARCHY_VM_CASE/inspection.sock" \
  WORKER_ALIAS
```

Stage `native/inspect-worker-allocation.py` in an operator-owned guest directory.
The client requires FreeBSD root, a canonical mode-0600 socket and a root socket
peer. Configure its exact Python/script/`--socket` argv as the separate
`inspection_command` in the guest's private worker-provisioner configuration.
Use the framework's configure/review/enable flow; source profiles cannot select
this configuration or endpoint. An inspection-only setup must retain an
allocation command that refuses, because this tool starts the worker explicitly.

## Expiry and evidence

Inspection and QMP reads have total deadlines, so dripping input cannot keep
renewing a socket timeout. Expiry ends inspection and requests guest ACPI power
off. Shutdown gets 30 seconds, then termination gets 10 seconds before a forced
kill. The terminal record retains the actual child status and reason; failed
child status propagates to the supervisor command. Signal interruption also
cleans up the owned child and inspector socket. Evidence directories are retained.

Original privileged tests remain trusted. This worker ownership boundary does
not contain arbitrary privileged code. Native acceptance must still verify the
exact installed framework, complete original cases, independent acceptance,
cleanup, source/SDK provenance and package custody.
