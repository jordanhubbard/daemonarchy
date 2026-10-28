# Remote build worker (design note)

Status: the worker, the client, the rc.d service and the sample recipes are
implemented in `tools/worker/`, with hosted tests. They are deployed on the three
project builders, which have run sample workloads only
([testing record](testing-remote-worker-20261028.md)). No real build has run
through the worker yet. Tracked as [WORKER-001](roadmap/active-work.md),
targeted at 1.4.0. [Implementation](#implementation) records the choices and
the remaining gaps.

Daemonarchy builds take hours: a world build is about 3.5 hours on the
FreeBSD builder, and a candidate with its VM checks takes most of a day. Today
the session that starts a build also supervises it. That session runs the
next step, waits on the current one and records the evidence. Closing that
session, or rebooting the machine it runs on, stops the work between steps,
even though each step runs detached on the builder.

The remote worker moves supervision onto the builder. A client submits a job
and disconnects. Any client holding an authorized key can reconnect later to
read status, follow the log, pause, resume or cancel, without interrupting the
job.

The worker ships in Daemonarchy 1.4 as part of the release, not as a private
tool for the project's own builders. Daemonarchy is developed in the open: any
Daemonarchy system can be a build worker, and anyone can rebuild the release
with the same commands and recipes the project uses. It is installed on every
system and off until the owner enables it and authorizes a key.

## Goals

- Jobs run to completion with no client connected. A client may disconnect
  and reconnect at any time.
- Every control action goes over SSH, and the worker adds no network
  listener. A key that is not authorized can do nothing.
- Pause, resume, cancel and retry have defined behaviour, including across a
  reboot of the builder.
- Long pipelines are checkpointed by step, so a failure, cancel or reboot
  costs the current step, not the whole pipeline.
- A worker key that leaks cannot run arbitrary commands.
- Outputs and logs stay on the builder until fetched and explicitly pruned.
- Off by default. An installed system runs no worker service and accepts no
  worker key until its owner enables both.
- No technique that only the project's own machines can use: the release is
  built through the same shipped worker, recipes and documentation.

## Non-goals (first version)

- Scheduling across hosts in the planned 1.4. Each builder has its own queue; a client queries
  several builders. A coordinator can come later (see
  [PERF-002](roadmap/active-work.md)).
- Signing or publishing. Signing keys never reach a worker; the operator signs
  fetched outputs.
- Replacing LitAI workers. `litai worker` registers SSH workers and runs
  controller-authored requests synchronously. This worker supplies the
  durable job layer that a LitAI controller could later submit to.

## Model

**Recipe.** A named, versioned pipeline kept in the product repository under
`tools/worker/recipes/` and installed with the worker.
Third-party recipes are out of scope for 1.4. A recipe lists steps; each step has a command (a
script in the repository, never text from the client), declared parameters
and their types, declared outputs, a resource class and whether it may be
retried. Planned first recipes:

- `src-world-kernel`
- `release-sets`
- `live-iso`
- `hwtrace-image`
- `poudriere-bulk`
- `vm-qualify`

**Job.** One run of a recipe at pinned commits: product, src, ports and any
other input repository. A job also carries the parameter values the recipe
allows, such as a target architecture, a name like `live6` or `dev8`, or a
queue file. The worker fetches the pinned commits itself and records their
hashes; a job never runs a client's working tree.

**Step.** The unit of checkpointing. A step is done when it exits 0 and its
declared outputs exist; the worker then records their SHA-256 in the job.
`resume` starts from the first step that is not done. A step whose inputs
changed since its record (a hash mismatch) runs again.

**Job directory**, on the builder under `/usr/daemonarchy/worker/jobs/<id>/`:

| Path | Contents |
|---|---|
| `job.json` | recipe, version, pinned commits, parameters, submitter key fingerprint, timestamps |
| `state` | `queued`, `running`, `pausing`, `paused`, `draining`, `cancelling`, `cancelled`, `failed`, `done`, `interrupted` |
| `steps/<n>.json` | per step: state, start and end, exit status, output hashes |
| `log/<n>.log` | per-step output; `log/job.log` is the merged view |
| `out/` | declared outputs |
| `work/` | scratch space, removed by `prune` |

## States

```
queued -> running -> done
running -> failed | cancelled | paused | interrupted
running -(drain)-> draining -> paused     (after the current step)
paused -(resume)-> running
interrupted -(resume or auto-resume)-> running
failed -(retry [step])-> running
```

- **pause:** sends SIGSTOP to the job's process group. Takes effect at once and
  holds memory and locks, so it suits short breaks. A builder reboot turns a
  paused job into `interrupted`.
- **drain:** lets the current step finish, then parks the job in `paused` with
  no process left. Use it before maintenance on the builder.
- **resume:** sends SIGCONT to a frozen job, or restarts a drained or
  interrupted job at the next step that is not done.
- **cancel:** SIGTERM to the process group, SIGKILL after a grace period, then
  the step's own cleanup hook, which, for example, detaches memory disks and
  unmounts the build's file systems.
- **retry [step]:** marks that step and every later step not done, then
  resumes.

Each job runs in its own process group, under a supervisor process started
by the rc.d service through `daemon(8)`. Steps that start a poudriere jail or a
VM must register their cleanup with the step, so cancel and interrupt leave no
jail, VM or memory disk behind.

## Interface

One command on the builder, `daemonarchy-worker`, serves every action. The
client `daemonarchy-remote` runs it over SSH:

```sh
daemonarchy-remote HOST submit RECIPE --pin product=SHA --pin src=SHA [--param k=v ...]
daemonarchy-remote HOST list [--all]
daemonarchy-remote HOST status JOB          # one screen: state, steps, times, ETA from history
daemonarchy-remote HOST log JOB [-f] [--step N]
daemonarchy-remote HOST pause|drain|resume|cancel JOB
daemonarchy-remote HOST retry JOB [--from-step N]
daemonarchy-remote HOST fetch JOB [PATH ...] --to DIR   # streams a tar of out/
daemonarchy-remote HOST prune JOB
daemonarchy-remote all list                 # every builder in the client's config
```

Requests and replies are JSON lines, with `--json` for agents and readable text
otherwise. `log -f` streams until the client disconnects; disconnecting never
signals the job. ETAs come from the recorded durations of earlier runs of the
same recipe step on that host.

## Security

- **Transport:** OpenSSH only. The worker opens no socket reachable from the
  network.
- **Forced command:** each worker key in the build user's `authorized_keys`
  is
  `restrict,command="/usr/local/bin/daemonarchy-worker serve --key NAME" ssh-ed25519 ...`.
  `restrict` turns off PTYs and port, agent and X11 forwarding. The
  key can only speak the worker protocol, which accepts actions on named
  recipes with typed parameters. No action runs client-supplied text.
- **Roles per key:** `read` (list, status, log, fetch), `operate` (adds pause,
  drain, resume, cancel, retry and prune) and `submit`. The roles are listed
  in `/usr/local/etc/daemonarchy-worker/keys.conf`, which is root-owned.
  Every action is logged with the key name and fingerprint.
- **Privilege:** jobs run as the unprivileged `dbuild` user. The few steps
  that need root (installworld into a staging root, mdconfig, poudriere,
  bhyve) call fixed wrapper scripts allowed by name in `sudoers`, with
  argument checks in the wrappers.
- **Inputs:** commits are fetched by the worker from the configured remotes
  and pinned by SHA. A parameter cannot name a path outside the job directory.
- **Secrets:** no signing keys, tokens or credentials are kept on workers.
  Recipes that need a distfile behind authentication take it as a fetched
  input from the operator.
- **Administration:** a separate admin key with a normal shell is kept for
  host maintenance and is never used by tooling.

Threats considered:

- a leaked worker key: limited to the recipes and roles granted to it, with
  no shell
- a malicious parameter: typed, path-confined
- a compromised repository commit: same exposure as building it by hand
- a stuck job: cancel, then the cleanup hooks
- disk exhaustion: per-host free-space floor checked before each step, and
  `prune`

## On an installed system

The planned 1.4 media installs `daemonarchy-worker` and `daemonarchy-remote`,
the rc.d service (`daemonarchy_worker_enable="NO"`), the recipes and a
manual page. The service is not enabled. The `dbuild` user and the sudo
wrappers are created only on enable:

```sh
daemonarchy-worker enable                 # creates dbuild, job root, sudo wrappers; enables rc.d
daemonarchy-worker key add NAME --role operate,submit < key.pub
daemonarchy-worker key list | remove NAME
daemonarchy-worker disable                # drains jobs, removes keys from authorized_keys, disables rc.d
```

`daemonarchy-remote` works from any system with `ssh` and `jq`, including
Linux and macOS, so a developer machine needs no Daemonarchy install to
drive a worker.

A worker needs FreeBSD's build prerequisites (source trees fetched by the
worker, poudriere for package recipes, bhyve for VM recipes). `daemonarchy-worker
doctor` reports what a recipe needs that the host lacks.

## Project hosts

Planned first deployment:

- the amd64 FreeBSD builder
- the KVM-hosted FreeBSD builder VM, once the operator approves installing on it
- the aarch64 FreeBSD worker

Private addresses stay in the client's private config, never in the
repository.

## Delivery plan

The worker is planned as a 1.4.0 deliverable: steps 1 to 3 are required before the 1.4
selection is locked, and step 4 by the 1.4.0 release.

1. This note, and the WORKER-001 work item.
2. `daemonarchy-worker` and `daemonarchy-remote`, in POSIX sh with `jq`, or
   Python 3 if a step's needs outgrow sh; rc.d service; `keys.conf`; recipe
   format; `src-world-kernel` and `hwtrace-image` recipes. Hosted tests
   with a fake recipe cover every state transition: pause, drain, resume,
   cancel, retry, interrupt and auto-resume after a simulated reboot, and
   refused actions per role.
3. Install on the amd64 FreeBSD builder. Run a real `src-world-kernel` job, disconnect,
   reconnect, drain, resume, reboot the builder mid-step and resume. Record
   the evidence. Add the worker to the image payload and the installer, off
   by default; document it in `getting-started.md` and `HACKING.md`; and
   check on the candidate image that it is installed and not enabled.
4. The `release-sets`, `live-iso`, `poudriere-bulk` and `vm-qualify` recipes,
   then a full candidate run through the worker alone. The planned 1.4.0
   release notes name the worker and point at this procedure.

## Implementation

The first implementation covers delivery steps 2 and 3, using sample workloads.

### Files

| Path | Installed as |
|---|---|
| `tools/worker/daemonarchy-worker` | `/usr/local/bin/daemonarchy-worker` (builder side; forced command, admin, rc.d hooks, supervisors) |
| `tools/worker/daemonarchy-remote` | `/usr/local/bin/daemonarchy-remote` (client; needs only `ssh`, `jq`, `tar` and a SHA-256 tool) |
| `tools/worker/rc.d/daemonarchy_worker` | `/usr/local/etc/rc.d/daemonarchy_worker` (`daemonarchy_worker_enable="NO"` by default) |
| `tools/worker/recipes/` | `/usr/local/share/daemonarchy-worker/recipes/` (read-only) |
| `tools/worker/worker.conf.sample` | `/usr/local/etc/daemonarchy-worker/worker.conf.sample` |
| `tools/worker/install.sh` | installs the above under `DESTDIR`; enables nothing |
| `tests/remote-worker.sh` | hosted test, run by `.github/workflows/remote-worker.yml` with shellcheck |

### Language

The worker and the client are written in POSIX sh with `jq`. Python 3 is not
used, for three reasons:

- The client has to run on a stock Linux, macOS or FreeBSD machine with
  only `ssh` and `jq`, and Python 3 is not always installed there.
- The builders are not uniform: the amd64 builder has `python3.12` but no
  `python3`.
- Every hard part of the worker uses base-system tools. `daemon(8)` (or
  `setsid(1)` on Linux) starts processes in a new session, `kill` signals a
  process group, `mkdir` makes an atomic lock, and `jq` reads and writes the
  JSON state.

sh would have become unwieldy if requests were parsed in the shell. Instead,
every request field goes through `jq` and is checked with `case` patterns,
which match the whole string, newlines included. Nothing the client sends is
ever evaluated.

### Protocol

- **Requests.** A request is one JSON object, which the client passes as the
  SSH command. sshd puts it in `SSH_ORIGINAL_COMMAND`, and the forced command
  `daemonarchy-worker serve --key NAME` parses it with `jq`. Anything that
  is not a JSON object with a known `op` is refused with exit status 3. That
  covers an empty command (a login), `sh -c ...`, `sftp` and `scp`.
- **Replies.** Replies are single JSON objects. Two operations stream
  instead: `log` without `-f` sends the raw text, and `fetch` sends a tar of
  `out/`.
- **Following a log.** `log -f` sends JSON lines (`line`, `hb`, `end`) and a
  heartbeat every 5 seconds while the job is quiet. When the client
  disconnects, the next heartbeat fails to write and the follower exits.
  Following never touches the job.
- **Roles.** `read` allows hello, recipes, list, status, log and fetch.
  `operate` adds pause, drain, resume, cancel, retry and prune. `submit`
  allows submit. A key with `operate` or `submit` can also read.
- **Audit.** Every request is logged with its key name and fingerprint in
  `JOB_ROOT/var/audit.log`.
- **Hardening.** `authorized_keys` and `.ssh` are generated from `keys.conf`
  by `key add/remove` and owned by root. The worker's home is the job root,
  also owned by root, so a job running as `dbuild` cannot add a key.
- **Typed parameters.** Parameters are `int` (with a range), `enum`, `bool`,
  `name`, `sha` and `path`. A `path` parameter is a relative path with no
  empty, `.` or `..` component, and the step receives it as an absolute path
  under the job's `work/`.
- **Pins and step environment.** Pins name inputs the recipe declares, and
  their remote URLs come only from the builder's `worker.conf`. Each step
  runs under `env -i`, with its parameters as `P_<name>` and its pins as
  `PIN_<name>`.

### Recipe format

A recipe is `recipes/NAME.json`:

- `name` and `version`
- `params`: name to `{type, default, min, max, values, help}`
- `inputs`: name to `{required}`
- `min_free_mb`
- `requires`: `{commands, paths}`, which `doctor` checks
- `steps`: each step has a `name` and a `run` script relative to `recipes/`.
  It can also give `env` (fixed by the recipe), `outputs` (relative to
  `out/`), a `cleanup` script, `retry` and `resource`.

On submit, the recipe and its scripts are copied into the job, so a job is
not affected by a later install.

There are three recipes:

- `sample`: three short steps. It can fail on demand, either always or only
  once, and writes a small output.
- `sample-long`: ten steps of `step_seconds` each, 60 seconds by default.
- `src-world-kernel`: fetches the pinned src commit, then runs buildworld
  and buildkernel, a `-DNO_ROOT` install into a staging root, and builds
  `base.txz` and `kernel.txz`. It has not been run yet.

### Supervision

`submit` and `resume` start a per-job supervisor with `daemon -f`, or
`setsid -f` on Linux. The supervisor starts each step runner the same way, so
the step runner leads its own session and process group, and its PID is the
group ID.

- **Checking steps.** The supervisor checks each second for the step's exit
  file and whether its process group is alive.
- **Pause and cancel.** Pause sends SIGSTOP to the group. Cancel sends
  SIGTERM and SIGCONT, then SIGKILL after `cancel_grace` seconds, then runs the
  step's cleanup hook. The hook also runs when a step fails or is
  interrupted.
- **Finishing a step.** A step is done when it exits 0 and every declared
  output exists. The worker then records the output's SHA-256. Before each
  step, it checks the hashes of the steps already done, and reruns from any
  step whose output changed.
- **Queue.** `max_jobs` jobs run at once; the rest stay `queued`. An explicit
  `resume` or `retry`, or an auto-resume, starts at once.
- **Free space.** A step does not start below `free_floor_mb`, or below the
  recipe's `min_free_mb`.

### Reboot and stop

The rc.d `start` runs `daemonarchy-worker boot` as the worker user. Any job in
an active state (`running`, `pausing`, `paused` frozen, `draining` or
`cancelling`) whose supervisor is not alive in the current boot becomes
`interrupted`. The worker kills what is left of the current step's process
group and runs the step's cleanup hook.

What happens next depends on the state before the reboot:

| State before the reboot | After |
|---|---|
| `running` | `interrupted`, then auto-resumed at its first step that is not done |
| `paused` (frozen) | `interrupted`; waits for `resume` |
| `draining` | `interrupted`; waits for `resume` |
| `paused` (drained) | stays `paused`; no process was left |
| `cancelling` | `cancelled` |

A frozen job matches the design: a reboot turns it into `interrupted`. The
design does not say whether an interrupted job that the operator had paused
or was draining should auto-resume. Auto-resuming it would undo the
operator's pause or the drain before maintenance, so it waits for `resume`.

The rc.d `stop` (also at shutdown) interrupts live jobs in the same way, so
running jobs resume at the next start.

"Alive in the current boot" compares a boot id stored with the supervisor:

- **With /proc.** Linux, and FreeBSD with linprocfs mounted at `/proc`, use
  `/proc/sys/kernel/random/boot_id`.
- **Without /proc.** Otherwise the first worker process after a boot writes
  a random id to `/var/run/daemonarchy-worker/boot_id`. `rc.d/cleanvar`
  deletes files under `/var/run` at boot.
- **Not used.** `kern.boottime` moves when the clock is stepped, so it would
  make live supervisors look dead.

### Gaps before a real release build

- `src-world-kernel` has not run on a builder. The `hwtrace-image`,
  `release-sets`, `live-iso`, `poudriere-bulk` and `vm-qualify` recipes do
  not exist.
- The root wrappers listed in `sudoers` (installworld into a staging root,
  mdconfig, poudriere, bhyve) are not implemented. Only unprivileged recipes
  can run.
- A reboot of a builder mid-step is covered only by the hosted simulation.
  No builder has been rebooted with a job running.
- The worker is not yet part of the image payload or the installer, and has
  no manual page. `getting-started.md` and `HACKING.md` do not describe it.
- ETAs come from the last five durations of each recipe step on the host. A
  first run has no ETA.
- `fetch` can run while a job is running. It returns whatever is in `out/`
  at that moment, and the client checks each file against the hashes
  recorded so far.
