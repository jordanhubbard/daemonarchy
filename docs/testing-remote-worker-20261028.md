# Remote build worker: hosted tests and sample workloads, October 28

This record covers the first implementation of
[WORKER-001](roadmap/active-work.md), described in
[the design and implementation note](remote-worker.md). The worker ran
**sample workloads only**: no real build, release input or signed artifact
went through it. Private builder addresses are left out; the client's private
configuration names them.

## Hosted tests

`sh tests/remote-worker.sh` runs a fake builder in a temporary directory.
A fake `ssh` plays the part of sshd. It looks up the client's key in the
generated `authorized_keys` and requires the `restrict,command="..."` form.
It runs that forced command with `SSH_ORIGINAL_COMMAND` set, in a session of
its own. A reboot is simulated by killing every supervisor and step process
group, changing the boot id and running the rc.d `start` hook
(`daemonarchy-worker boot`). The recipes are installed read-only, as
`install.sh` installs them.

Result on Linux (dash as `/bin/sh`): **126 passed, 0 failed**, in about 50
seconds. The test ran six times while being developed, and the last three
runs passed in full. CI runs it with `shellcheck`
(`.github/workflows/remote-worker.yml`).

| Area | Checks |
|---|---|
| Keys | Every `authorized_keys` line is `restrict` plus the forced command. `key add` refuses a key line with options and refuses an unknown role. |
| Forced command | Refused: `sh -c id`, an empty command (a login), a JSON array, an unknown op, an op with shell characters, a key that is not in `keys.conf`. |
| Roles | A read key cannot submit, pause, cancel or prune. An operate key cannot submit. A submit-only key cannot cancel or retry. An operate key can read. |
| Confinement | `path` parameters refused: `../x`, `/etc/passwd`, `a/../../b`, `a//b`, `.`, `notes/`, `./x`, `a/./b`, `x y`. Fetch of `../job.json` or `/etc` refused. A job id with `..` refused. A recipe name with `/` refused. |
| Typed parameters | Refused: an unknown parameter, an int out of range, `1;id`, an enum value of `$(id)`, a name of `` `id` ``, a newline smuggling a second parameter, an undeclared or short pin, a missing required pin. No refused submit leaves a job directory behind. |
| States | queued → running → done. running → failed, then retry from the failed step, keeping earlier steps. Retry `--from-step 1` of a done job. running → paused (frozen) → running. running → draining → paused (drained) → running. running → cancelling → cancelled, then retry `--from-step`. queued → cancelled. paused (drained) → cancelled. |
| Checkpoints | A done step whose output hash changed runs again. Pause stops every process in the step's group, and a frozen step writes nothing. Resume does not restart the step. |
| Cleanup hook | Runs on fail, cancel and interrupt. |
| Reboot | After a simulated reboot, status flags a running job as having no supervisor, and rc start auto-resumes it. The interrupted step reruns as attempt 2 and earlier steps are kept. A frozen job becomes `interrupted` and waits for `resume`. A drained job stays `paused`. |
| `log -f` | The client's session is killed. The worker's follower exits within a few heartbeats, and the job keeps running. |
| Other | The queue holds a second job while one runs (`max_jobs=1`). Prune of a live job is refused. Prune removes `work/` and keeps `out/`, and `--all` removes the job. `disable` refuses every key, empties `authorized_keys` and drains the running job. |

## Deployment

Each builder ran `tools/worker/install.sh` and then `daemonarchy-worker enable`,
which creates the `dbuild` user. The worker was at commit `301ad2a`; the amd64
builder had `61a4316` first, and was updated after the bug described below. One client key was registered with
`daemonarchy-worker key add jkh-agent --role read,operate,submit`.
`daemonarchy-worker doctor` passed every check on all three hosts.

| Builder | OS | Job root | Boot id source |
|---|---|---|---|
| amd64 FreeBSD builder | 16.0-CURRENT amd64 | `/usr/daemonarchy/worker` (dataset `zroot/daemonarchy`) | linprocfs `/proc` |
| KVM-hosted builder guest (`fast`) | 16.0-CURRENT amd64 | `/home/daemonarchy-worker` (outside the boot environment) | linprocfs `/proc` |
| aarch64 worker | 16.0-CURRENT arm64 | `/home/daemonarchy-worker` (outside the boot environment) | `/var/run/daemonarchy-worker/boot_id` |

On every host, `/usr/daemonarchy/worker/.ssh` or `/home/daemonarchy-worker/.ssh`,
its `authorized_keys` and the job root itself are owned by root, and `jobs/`
and `var/` are owned by `dbuild`. The rc.d service is enabled
(`daemonarchy_worker_enable=YES`).

The first submit on the amd64 builder found a bug. Recipe scripts install as
`0444`, and the three `sample` steps share `sample/step.sh`, so the second
copy into the job failed and left a partial job directory. The worker now
copies a shared script once and removes a failed submit's job directory, and
the hosted test uses read-only recipes.

## Sample workloads

### `sample` on each builder

Each builder ran `sample` with `--param delay=2 --param label=<host>`. Each
job finished all three steps. The client fetched `out/`, and both outputs
matched the SHA-256 the worker had recorded.

| Builder | Job | `sample-output.txt` SHA-256 | Last output line |
|---|---|---|---|
| amd64 builder | `20261028T210951Z-sample-62c0a2` | `c9428e0386bf930a00f40e2d399b4af1600c40c491b8ce3ef51efc251afd8b3c` | `daemon-amd64 computed amd64` |
| `fast` guest | `20261028T211056Z-sample-58fe76` | `b0c10737fe4f24f5458be62baca6b1fcbc914f320ca5c8f2f662d9ee7085889b` | `fast-guest computed amd64` |
| aarch64 worker | `20261028T141234Z-sample-fa4a24` | `5dc244eb5fe8fb636bc4ef20a52bc3e5c03d9920a391221cc998c8fad1a41462` | `barmy-aarch64 computed arm64` |

The aarch64 worker's job id says 14:12Z for a job submitted at 21:12 UTC:
that host's clock runs seven hours behind. `daemonarchy-remote all list`
showed all three jobs as `done`.

### `sample-long` control sequence on the amd64 builder

Job `20261028T211346Z-sample-long-41a9fd`: ten steps of 60 s each.

| Time (UTC) | Action | Observed |
|---|---|---|
| 21:13:46 | submit | started from the queue; step 1 running |
| 21:14:06 | `log -f` for 25 s, then the client was killed (`timeout`, exit 124) | streamed steps 1 at 5 s intervals |
| 21:14:39 | builder: `pgrep -lf "daemonarchy-worker serve"` | `none`: the follower exited after the disconnect |
| 21:14:39 | reconnect: `status`, then `log -f` again for 8 s | still `running`; the follow resumed, and showed step 1 done in 61 s and step 2 starting |
| 21:14:48 | `pause` | `paused (frozen)`; the step's group leader in state `Ts`; the step log stayed at 43 bytes for 20 s |
| 21:15:09 | `resume` | `running`; group leader `Ss`; step 2 not restarted, done in 1m21s (60 s plus the 20 s pause) |
| 21:15:09 | `drain` | `draining`; step 2 finished, then `paused (drained)`; no supervisor or step process left for the job |
| 21:16:09 | `resume` | restarted at step 3, the first step not done |
| 21:16:25 | `cancel` mid-step 3 | `cancelled`; step 3 `cancelled`; the step log ends with `cleanup hook: step 3 (tick-03) result cancelled` |
| 21:16:30 | `retry --from-step 3` | `running`; steps 1 and 2 kept |
| FINISH_TIME | finished | FINISH_RESULT |

On the `fast` guest, a short `sample-long` job (`step_seconds=20`) was paused
to capture the whole process group. All six members were stopped: the step
runner, its subshell, `tee`, `awk`, the step script and its `sleep`. After
`resume` all six were running again. `cancel` then left no process for the
job, the cleanup hook exited 0, and `prune --all` removed the job.

### The forced-command key cannot get a shell

These commands used the client key against the amd64 builder's real sshd.

| Attempt | Result |
|---|---|
| `ssh -i KEY dbuild@builder` (login) | `{"ok":false,"error":"bad_request",...}`, exit 3 |
| `ssh ... 'sh -c id'`, `ssh ... id`, `ssh ... '/bin/sh -i'` | the same refusal, exit 3 |
| `ssh -tt ...` | `PTY allocation request failed on channel 0`, exit 255 |
| `ssh -o ExitOnForwardFailure=yes -R 0:127.0.0.1:22 ...` | `remote port forwarding failed`, exit 255 |
| `ssh -W 127.0.0.1:22 ...` | `administratively prohibited`, then `stdio forwarding failed` |
| `sftp ...`, `scp dbuild@builder:/etc/passwd .` | the session gets the JSON refusal instead of a protocol, and no file is copied |
| submit with `label` = `$(id)` | `invalid_param: label must be a name` |
| submit with `note` = `../../../../etc/passwd` | `invalid_param: note must be a relative path inside the job directory` |
| fetch of job `../../../etc` | `bad_request: malformed job id` |
| `'{"op":"status","job":"x"}; id'` | `bad_request`: not a JSON object |

### Reboot test

**Not run.** The aarch64 worker is the only builder approved for a reboot,
and it was not idle during this session: another agent was building upstream
`src.txz` sets there (a base pass and then a patched pass). The rule for this
round allows a reboot only when that host runs nothing else important, so
reboot recovery is covered only by the hosted simulation. The aarch64 worker
is also the host where a reboot would test the `/var/run` boot id rather
than linprocfs.

## Not covered

- `src-world-kernel` was written and not run. `hwtrace-image` and the other
  build recipes do not exist, and neither do the root wrappers.
- No builder was rebooted with a job running.
- Real workloads were not moved to the worker.
- Nothing was signed or published.
