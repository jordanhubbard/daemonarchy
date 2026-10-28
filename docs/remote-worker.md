# Remote build worker (design note)

Status: design, not implemented. Tracked as [WORKER-001](roadmap/active-work.md),
targeted at 1.4.0.

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

- Scheduling across hosts in 1.4. Each builder has its own queue; a client queries
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

The 1.4 media installs `daemonarchy-worker` and `daemonarchy-remote`,
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

The worker is a 1.4.0 deliverable: steps 1 to 3 are required before the 1.4
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
   then a full candidate run through the worker alone. The 1.4.0 release
   notes name the worker and point at this procedure.
