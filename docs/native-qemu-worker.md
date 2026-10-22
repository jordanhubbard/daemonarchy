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

For the retained secondary-account backend, verify that the actual workspace
filesystem supports POSIX.1e ACLs before capturing inputs or starting a build.
The first installed source lifecycle attempt reached ACL setup after 860.693
seconds, then refused with errno 45 because the disposable UFS image had ACLs
disabled. On a dedicated disposable UFS guest, enable the `acls` mount option
while retaining the other selected mount options; verify an actual named-user
`setfacl` grant, read it back, and remove it. A successful `getfacl` of ordinary
mode bits alone does not prove support. This backend requires POSIX ACLs; an
NFSv4 ACL filesystem needs a separately qualified backend or a dedicated supported
workspace volume. Do not change a physical worker's filesystem policy implicitly.

The [source SDK build checkpoint](../verification/native-sdk-build-development.json)
boots a separate owned KVM guest with eight CPUs, 16 GiB RAM and a 160 GiB disk.
An unprivileged four-job native make baseline has started from the pinned source
fork, requesting world, kernel, pkgbase packages and installer sets. The original
cold image remains unchanged. Completion, source-built SDK admission and equivalent
clean/warm/change performance measurements remain required. This guest does not
replace the separately running installed lifecycle check.

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

Termination, interrupt and hangup signals revoke inspection and request shutdown
through the supervisor loop. Repeated signals cannot interrupt its existing
bounded cleanup, so the owned child is reaped before terminal evidence is
published. An interrupted supervisor returns status 130; terminal evidence keeps
the actual child status. Controller fake-QMP regression checks cover repeated
signals during delayed shutdown. These checks do not replace actual VM or
installed-lifecycle qualification.

Original privileged tests remain trusted. This worker ownership boundary does
not contain arbitrary privileged code. Native acceptance must still verify the
exact installed framework, complete original cases, independent acceptance,
cleanup, source/SDK provenance and package custody.
