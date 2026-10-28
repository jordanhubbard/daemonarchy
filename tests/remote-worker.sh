#!/bin/sh
# shellcheck disable=SC2016,SC1010
# Hosted tests for the remote build worker (WORKER-001, docs/remote-worker.md).
#
# A fake builder lives in a temporary directory.  A fake ssh plays sshd: it
# finds the client's key in the generated authorized_keys, insists on the
# restrict,command= form and runs that forced command with
# SSH_ORIGINAL_COMMAND set, in a session of its own as sshd would.  Reboots
# are simulated by killing every supervisor and step and changing the boot id.
#
# Needs: sh, jq, setsid, ssh-keygen, tar, sha256sum.  Runs in about 3 minutes.

set -u

here=$(cd "$(dirname "$0")/.." && pwd)
W=$here/tools/worker/daemonarchy-worker
REMOTE=$here/tools/worker/daemonarchy-remote

T=$(mktemp -d "${TMPDIR:-/tmp}/remote-worker-test.XXXXXX")
ROOT=$T/root
ETC=$T/etc
mkdir -p "$ETC" "$T/bin" "$T/keys"
echo boot-1 >"$T/bootid"

pass=0
failed=0
ok() {
	pass=$((pass + 1))
	printf 'ok %s - %s\n' "$pass" "$1"
}
not_ok() {
	failed=$((failed + 1))
	printf 'not ok - %s\n' "$1"
	[ $# -gt 1 ] && printf '#   %s\n' "$2"
}
check() {
	# check DESCRIPTION COMMAND...
	d=$1
	shift
	if "$@" >/dev/null 2>&1; then ok "$d"; else not_ok "$d" "$*"; fi
}

kill_everything() {
	for f in "$ROOT"/jobs/*/run.json; do
		[ -f "$f" ] || continue
		p=$(jq -r '.supervisor_pid // empty' "$f")
		[ -n "$p" ] && kill -s KILL "$p" 2>/dev/null
	done
	for f in "$ROOT"/jobs/*/steps/*.pgid; do
		[ -f "$f" ] && kill -s KILL -- "-$(cat "$f")" 2>/dev/null
	done
	[ -f "$T/serve.pids" ] && while read -r p; do kill -s KILL -- "-$p" 2>/dev/null; done <"$T/serve.pids"
	return 0
}
cleanup() {
	kill_everything
	sleep 0.5
	kill_everything
	chmod -R u+w "$T" 2>/dev/null
	rm -rf "$T"
}
trap cleanup EXIT INT TERM

# Recipes installed read-only, as install.sh installs them.
cp -R "$here/tools/worker/recipes" "$T/recipes"
find "$T/recipes" -type f -exec chmod 0444 {} +
cat >"$ETC/worker.conf" <<EOF
job_root=$ROOT
recipes_dir=$T/recipes
max_jobs=1
free_floor_mb=1
cancel_grace=2
cleanup_timeout=20
heartbeat=1
EOF
export DAEMONARCHY_WORKER_CONF="$ETC/worker.conf"
export DAEMONARCHY_WORKER_FAKE_ADMIN=1
export DAEMONARCHY_WORKER_BOOT_ID=boot-1

# --- fake sshd: authorized_keys forced command, own session ---------------
cat >"$T/bin/fake-ssh" <<'EOF'
#!/bin/sh
# Called as the client calls ssh: [options...] USER@HOST REQUEST
for last; do :; done
req=$last
dest=
prev=
for a; do
	[ "$a" = "$req" ] && dest=$prev
	prev=$a
done
key=${dest%@*}
line=$(grep " daemonarchy-worker:$key\$" "$FAKE_ROOT/.ssh/authorized_keys") || {
	echo "Permission denied (publickey)." >&2
	exit 255
}
case $line in
restrict,command=\"*) ;;
*) echo "fake-ssh: key line lacks restrict,command=" >&2; exit 255 ;;
esac
cmd=${line#restrict,command=\"}
cmd=${cmd%%\"*}
exec env -i PATH="$PATH" DAEMONARCHY_WORKER_CONF="$DAEMONARCHY_WORKER_CONF" \
    DAEMONARCHY_WORKER_FAKE_ADMIN=1 DAEMONARCHY_WORKER_BOOT_ID="$(cat "$FAKE_BOOTID")" \
    SSH_ORIGINAL_COMMAND="$req" FAKE_PIDS="$FAKE_PIDS" \
    setsid -w /bin/sh -c 'echo $$ >>"$FAKE_PIDS"; exec /bin/sh -c "$1"' sh "$cmd"
EOF
chmod +x "$T/bin/fake-ssh"
export FAKE_ROOT="$ROOT" FAKE_BOOTID="$T/bootid" FAKE_PIDS="$T/serve.pids"
export DAEMONARCHY_REMOTE_SSH="$T/bin/fake-ssh"
export DAEMONARCHY_REMOTE_CONF="$T/remote.conf"
cat >"$T/remote.conf" <<EOF
# NAME DEST options
agent     agent@fake      identity=$T/keys/agent
reader    reader@fake     identity=$T/keys/reader
operator  operator@fake   identity=$T/keys/operator
submitter submitter@fake  identity=$T/keys/submitter
stranger  stranger@fake   identity=$T/keys/stranger
EOF

R() { "$REMOTE" "$@"; }
RJ() { "$REMOTE" --json "$@"; }
st() { RJ agent status "$1" | jq -r .state; }
stepf() { RJ agent status "$1" | jq -r --argjson n "$2" --arg k "$3" '.steps[$n-1][$k] | tostring'; }
wait_state() {
	# wait_state JOB STATE SECONDS
	i=0
	while [ $i -lt $(($3 * 5)) ]; do
		[ "$(st "$1")" = "$2" ] && return 0
		sleep 0.2
		i=$((i + 1))
	done
	return 1
}
wait_step_running() {
	# wait_step_running JOB N SECONDS
	i=0
	while [ $i -lt $(($3 * 5)) ]; do
		[ "$(stepf "$1" "$2" state)" = running ] && return 0
		sleep 0.2
		i=$((i + 1))
	done
	return 1
}
submit() { RJ "$@" | jq -r .job; }
serve_raw() {
	# serve_raw KEY REQUEST: the forced command with an arbitrary request
	env SSH_ORIGINAL_COMMAND="$2" "$W" serve --key "$1"
}
refused() {
	# refused DESCRIPTION EXPECTED_ERROR COMMAND...: exit 3 and that error
	d=$1
	e=$2
	shift 2
	out=$("$@" 2>/dev/null)
	rc=$?
	got=$(printf '%s' "$out" | jq -r '.error // empty' 2>/dev/null)
	if [ $rc -eq 3 ] && [ "$got" = "$e" ]; then ok "$d"; else not_ok "$d" "rc=$rc out=$out"; fi
}

# --- enable and keys --------------------------------------------------------
check "enable creates the job root" "$W" enable --job-root "$ROOT"
for k in agent reader operator submitter stranger; do
	ssh-keygen -q -t ed25519 -N '' -C "$k" -f "$T/keys/$k"
done
"$W" key add agent --role read,operate,submit <"$T/keys/agent.pub" >/dev/null
"$W" key add reader --role read <"$T/keys/reader.pub" >/dev/null
"$W" key add operator --role read,operate <"$T/keys/operator.pub" >/dev/null
"$W" key add submitter --role submit <"$T/keys/submitter.pub" >/dev/null
check "four keys listed" test "$("$W" key list | wc -l)" -eq 4
check "every authorized_keys line is restrict + forced command" \
    sh -c "! grep -v '^#' '$ROOT/.ssh/authorized_keys' | grep -v '^restrict,command=\"$W serve --key [a-z]*\" ssh-ed25519 '"
check "key add refuses a key line with options" sh -c "! echo 'command=\"sh\" ssh-ed25519 AAAA x' | '$W' key add evil --role read"
check "key add refuses an unknown role" sh -c "! '$W' key add evil --role root <'$T/keys/stranger.pub'"
check "hello reports the key's roles" sh -c "'$REMOTE' --json reader hello | jq -e '.roles == [\"read\"]'"
check "doctor runs" sh -c "'$W' doctor | grep -q 'ok    jq installed'"

# --- refused requests: shell, unknown key, malformed ----------------------
refused "a shell command over the forced key is refused" bad_request serve_raw agent "sh -c id"
refused "an empty command (interactive login) is refused" bad_request serve_raw agent ""
refused "a JSON array is refused" bad_request serve_raw agent '["status"]'
refused "an unknown op is refused" bad_request serve_raw agent '{"op":"exec","cmd":"id"}'
refused "an op with odd characters is refused" bad_request serve_raw agent '{"op":"list;id"}'
refused "a key not in keys.conf is refused" forbidden serve_raw stranger '{"op":"list"}'
check "the audit log keeps a printable copy of a refused request" grep -q 'key=agent .*result=bad_request request="sh -c id"' "$ROOT/var/audit.log"
check "the client cannot reach a key with no authorized_keys line" sh -c "! '$REMOTE' stranger list"

# --- happy path: queued -> running -> done; fetch; ETA ---------------------
j1=$(submit submitter submit sample --param delay=1 --param label=first)
check "submit returns a job id" test -n "$j1"
check "sample job reaches done" wait_state "$j1" done 30
check "status lists hashes for declared outputs" sh -c "'$REMOTE' --json reader status '$j1' | jq -e '.steps[2].outputs[\"sample-output.txt\"] | length == 64'"
check "fetch verifies outputs against the recorded hashes" sh -c "'$REMOTE' reader fetch '$j1' --to '$T/fetch1' | grep -q '2 output(s) match'"
check "fetched output carries the label" grep -q 'label: first' "$T/fetch1/sample-output.txt"
check "fetch of one path" sh -c "'$REMOTE' reader fetch '$j1' compute.txt --to '$T/fetch2' && test -f '$T/fetch2/compute.txt' && test ! -f '$T/fetch2/sample-output.txt'"
check "log shows each step" sh -c "'$REMOTE' reader log '$j1' | grep -q '\[3 package\] sample step 3 (package) done'"
check "per-step log" sh -c "'$REMOTE' reader log '$j1' --step 2 | grep -q 'compute'"
check "list shows the job" sh -c "'$REMOTE' reader list | grep -q '$j1  done'"
check "audit log records key and fingerprint" grep -q "key=submitter fp=SHA256:.* op=submit job=$j1" "$ROOT/var/audit.log"
check "ETA comes from recorded history" sh -c "j=\$('$REMOTE' --json submitter submit sample --param delay=1 | jq -r .job); '$REMOTE' --json agent status \$j | jq -e '.eta_seconds != null'"
wait_state "$(RJ agent list | jq -r '.jobs[-1].id')" done 30

# --- refused actions per role ---------------------------------------------
refused "read key cannot submit" forbidden serve_raw reader '{"op":"submit","recipe":"sample"}'
refused "read key cannot pause" forbidden serve_raw reader "{\"op\":\"pause\",\"job\":\"$j1\"}"
refused "read key cannot cancel" forbidden serve_raw reader "{\"op\":\"cancel\",\"job\":\"$j1\"}"
refused "read key cannot prune" forbidden serve_raw reader "{\"op\":\"prune\",\"job\":\"$j1\"}"
refused "operate key cannot submit" forbidden serve_raw operator '{"op":"submit","recipe":"sample"}'
refused "submit key cannot cancel" forbidden serve_raw submitter "{\"op\":\"cancel\",\"job\":\"$j1\"}"
refused "submit key cannot retry" forbidden serve_raw submitter "{\"op\":\"retry\",\"job\":\"$j1\"}"
check "operate key can read status" sh -c "'$REMOTE' operator status '$j1' >/dev/null"

# --- path confinement and typed parameters --------------------------------
for bad in ../x /etc/passwd 'a/../../b' 'a//b' . 'notes/' './x' 'a/./b' 'x y'; do
	refused "path parameter '$bad' is refused" invalid_param \
	    serve_raw agent "$(jq -n -c --arg v "$bad" '{op:"submit",recipe:"sample",params:{note:$v}}')"
done
refused "fetch of ../job.json is refused" invalid_param serve_raw reader "{\"op\":\"fetch\",\"job\":\"$j1\",\"paths\":[\"../job.json\"]}"
refused "fetch of /etc is refused" invalid_param serve_raw reader "{\"op\":\"fetch\",\"job\":\"$j1\",\"paths\":[\"/etc\"]}"
refused "a job id with .. is refused" bad_request serve_raw reader '{"op":"status","job":"../../etc"}'
refused "a recipe name with / is refused" bad_request serve_raw agent '{"op":"submit","recipe":"../sample"}'
refused "an unknown recipe is refused" not_found serve_raw agent '{"op":"submit","recipe":"nope"}'
refused "an unknown parameter is refused" invalid_param serve_raw agent '{"op":"submit","recipe":"sample","params":{"cmd":"id"}}'
refused "an int out of range is refused" invalid_param serve_raw agent '{"op":"submit","recipe":"sample","params":{"delay":"9999"}}'
refused "a non-integer is refused" invalid_param serve_raw agent '{"op":"submit","recipe":"sample","params":{"delay":"1;id"}}'
refused "an enum outside its values is refused" invalid_param serve_raw agent '{"op":"submit","recipe":"sample","params":{"fail_mode":"$(id)"}}'
refused "a name with shell characters is refused" invalid_param serve_raw agent '{"op":"submit","recipe":"sample","params":{"label":"`id`"}}'
refused "a newline smuggling a second parameter is refused" bad_request serve_raw agent '{"op":"submit","recipe":"sample","params":{"label":"x\nfail_step\t3"}}'
refused "a pin for an undeclared input is refused" invalid_param serve_raw agent '{"op":"submit","recipe":"sample","pins":{"src":"0123456789012345678901234567890123456789"}}'
refused "a missing required pin is refused" invalid_param serve_raw agent '{"op":"submit","recipe":"src-world-kernel"}'
refused "a short pin is refused" invalid_param serve_raw agent '{"op":"submit","recipe":"src-world-kernel","pins":{"src":"abc123"}}'
mv "$T/recipes/sample/cleanup.sh" "$T/recipes/sample/cleanup.sh.away"
check "a recipe with a missing script fails the submit" sh -c "serve_out=\$(SSH_ORIGINAL_COMMAND='{\"op\":\"submit\",\"recipe\":\"sample\"}' '$W' serve --key agent); printf '%s' \"\$serve_out\" | jq -e '.message == \"recipe script sample/cleanup.sh missing\"'"
mv "$T/recipes/sample/cleanup.sh.away" "$T/recipes/sample/cleanup.sh"
check "no refused submit created a job" test "$(find "$ROOT/jobs" -mindepth 1 -maxdepth 1 -type d | wc -l)" -eq 2

# --- failed -> retry (from the failed step, earlier steps kept) -----------
j2=$(submit agent submit sample --param delay=0 --param fail_step=2 --param fail_mode=once)
check "a step failing on request fails the job" wait_state "$j2" failed 30
check "failed step 2 records exit 1" test "$(stepf "$j2" 2 exit)" = 1
check "cleanup hook ran for the failed step" grep -q '^2 compute failed$' "$ROOT/jobs/$j2/work/cleanup.log"
check "retry from the failed step" sh -c "'$REMOTE' operator retry '$j2' | grep -q 'retrying from step 2'"
check "retried job reaches done" wait_state "$j2" done 30
check "retry kept step 1 (one attempt)" test "$(stepf "$j2" 1 attempts)" = 1
check "retry reran step 2 (two attempts)" test "$(stepf "$j2" 2 attempts)" = 2
check "retry --from-step 1 on a done job reruns everything" sh -c "'$REMOTE' operator retry '$j2' --from-step 1 >/dev/null"
check "rerun reaches done" wait_state "$j2" done 30
check "step 1 ran twice" test "$(stepf "$j2" 1 attempts)" = 2
refused "retry of an unknown step is refused" invalid_state serve_raw agent "{\"op\":\"retry\",\"job\":\"$j2\",\"from_step\":\"9\"}"

# --- a changed output reruns its step on resume ---------------------------
echo tampered >>"$ROOT/jobs/$j2/out/compute.txt"
"$REMOTE" agent retry "$j2" --from-step 3 >/dev/null
wait_state "$j2" done 30
check "a done step whose output hash changed runs again" test "$(stepf "$j2" 2 attempts)" = 4
check "and the change is logged" grep -q 'output compute.txt changed' "$ROOT/jobs/$j2/log/job.log"

# --- pause (SIGSTOP) and resume -------------------------------------------
j3=$(submit agent submit sample-long --param step_seconds=2)
wait_step_running "$j3" 2 30
check "pause freezes the running step" sh -c "'$REMOTE' operator pause '$j3' | grep -q 'paused'"
check "state is paused (frozen)" sh -c "'$REMOTE' --json reader status '$j3' | jq -e '.state == \"paused\" and .run.paused_mode == \"frozen\"'"
pg=$(cat "$ROOT/jobs/$j3/steps/2.pgid")
check "every process in the step's group is stopped" sh -c "ps -o stat= -g '$pg' | grep -qv '^T' && exit 1 || exit 0"
size1=$(wc -c <"$ROOT/jobs/$j3/log/2.log")
sleep 3
check "a frozen step writes nothing" test "$(wc -c <"$ROOT/jobs/$j3/log/2.log")" -eq "$size1"
refused "pause of a paused job is refused" invalid_state serve_raw agent "{\"op\":\"pause\",\"job\":\"$j3\"}"
check "resume continues the step" sh -c "'$REMOTE' operator resume '$j3' | grep -q 'running'"
check "state is running again" test "$(st "$j3")" = running
check "step 2 was not restarted" test "$(stepf "$j3" 2 attempts)" = 1

# --- drain -> paused at the step boundary -> resume ------------------------
wait_step_running "$j3" 3 30
check "drain lets the step finish" sh -c "'$REMOTE' operator drain '$j3' | grep -q draining"
check "state is draining" test "$(st "$j3")" = draining
check "drained job parks in paused" wait_state "$j3" paused 30
check "parked as drained with no current step" sh -c "'$REMOTE' --json reader status '$j3' | jq -e '.run.paused_mode == \"drained\" and .run.current_step == null'"
check "step 3 finished before parking" test "$(stepf "$j3" 3 state)" = done
check "step 4 has not started" test "$(stepf "$j3" 4 state)" = pending
check "resume restarts at the next step" sh -c "'$REMOTE' operator resume '$j3' | grep -q 'first step not done'"
check "step 4 runs" wait_step_running "$j3" 4 30
check "step 3 kept one attempt" test "$(stepf "$j3" 3 attempts)" = 1

# --- log -f: a disconnecting client does not touch the job ----------------
: >"$T/serve.pids"
# The client runs in a session of its own, as on another machine; killing
# that session is a client that vanished without a word.
setsid sh -c "exec '$REMOTE' agent log '$j3' -f >'$T/follow.out' 2>&1" &
cpid=$!
sleep 3
check "log -f streams the job" grep -q 'tick-0' "$T/follow.out"
fpid=$(head -n 1 "$T/serve.pids")
check "the follow is being served" kill -s 0 "$fpid"
kill -s KILL -- "-$cpid"
gone=no
i=0
while [ $i -lt 20 ]; do
	if ! kill -s 0 -- "-$fpid" 2>/dev/null; then
		gone=yes
		break
	fi
	sleep 0.5
	i=$((i + 1))
done
check "the worker's follow exits once the client is gone" test $gone = yes
check "the job keeps running after the client left" test "$(st "$j3")" = running

# --- cancel: TERM, KILL, cleanup hook ---------------------------------------
# cancel just after a step starts, so it lands mid-step and not on a boundary
c=$(($(RJ agent status "$j3" | jq -r .run.current_step) + 1))
wait_step_running "$j3" "$c" 30
pg=$(cat "$ROOT/jobs/$j3/steps/$c.pgid")
check "cancel is accepted" sh -c "'$REMOTE' operator cancel '$j3' | grep -q cancelling"
check "cancelled job reaches cancelled" wait_state "$j3" cancelled 30
check "the step's process group is gone" sh -c "! kill -s 0 -- -$pg"
check "the running step is recorded cancelled" test "$(stepf "$j3" "$c" state)" = cancelled
check "cleanup hook ran for the cancelled step" grep -q "^$c tick-$(printf %02d "$c") cancelled\$" "$ROOT/jobs/$j3/work/cleanup.log"
check "retry --from-step after cancel" sh -c "'$REMOTE' operator retry '$j3' --from-step $c | grep -q 'from step $c'"
check "the retried step runs" wait_step_running "$j3" "$c" 30
check "earlier steps were kept" test "$(stepf "$j3" $((c - 1)) attempts)" = 1

# --- queue: max_jobs 1 -------------------------------------------------------
jq_=$(submit agent submit sample --param delay=0)
check "a second job waits in queued" test "$(st "$jq_")" = queued
check "cancel of a queued job" sh -c "'$REMOTE' operator cancel '$jq_' | grep -q cancelled"
jq2=$(submit agent submit sample --param delay=0)

# --- simulated reboot: interrupted -> auto-resume ---------------------------
r=$((c + 1))
wait_step_running "$j3" $r 30
kill_everything
sleep 0.5
echo boot-2 >"$T/bootid"
export DAEMONARCHY_WORKER_BOOT_ID=boot-2
check "before restart, status flags the job as having no supervisor" sh -c "'$REMOTE' --json reader status '$j3' | jq -e '.stale'"
"$W" boot >"$T/boot.out" 2>&1
check "rc start auto-resumes the running job" grep -q "auto-resumed $j3" "$T/boot.out"
check "the interrupt is logged" grep -q 'job interrupted (was running; auto-resume true)' "$ROOT/jobs/$j3/log/job.log"
check "cleanup hook ran for the interrupted step" grep -q "^$r tick-$(printf %02d $r) interrupted\$" "$ROOT/jobs/$j3/work/cleanup.log"
check "the interrupted step runs again" wait_step_running "$j3" $r 30
check "the interrupted step is on its second attempt" test "$(stepf "$j3" $r attempts)" = 2
check "the step before it was not rerun" test "$(stepf "$j3" "$c" attempts)" = 2
check "pause the resumed job before a second reboot" sh -c "'$REMOTE' operator pause '$j3' | grep -q paused"
kill_everything
echo boot-3 >"$T/bootid"
export DAEMONARCHY_WORKER_BOOT_ID=boot-3
"$W" boot >"$T/boot2.out" 2>&1
check "a paused job becomes interrupted across a reboot" test "$(st "$j3")" = interrupted
check "and waits for an explicit resume" sh -c "'$REMOTE' --json reader status '$j3' | jq -e '.run.auto_resume == false'"
check "resume restarts the interrupted job" sh -c "'$REMOTE' operator resume '$j3' | grep -q 'first step not done'"
check "interrupted -> running" test "$(st "$j3")" = running
check "sample-long completes" wait_state "$j3" done 60
check "the queued job ran after it" wait_state "$jq2" done 30
check "final output fetched" sh -c "'$REMOTE' reader fetch '$j3' sample-long-output.txt --to '$T/fetch3' && test \$(wc -l <'$T/fetch3/sample-long-output.txt') -eq 10"

# --- a drained job stays parked across a reboot -----------------------------
j4=$(submit agent submit sample-long --param step_seconds=1)
wait_step_running "$j4" 2 30
"$REMOTE" operator drain "$j4" >/dev/null
wait_state "$j4" paused 30
kill_everything
echo boot-4 >"$T/bootid"
export DAEMONARCHY_WORKER_BOOT_ID=boot-4
"$W" boot >/dev/null 2>&1
check "a drained job stays paused after a reboot" test "$(st "$j4")" = paused
check "cancel of a drained job" sh -c "'$REMOTE' operator cancel '$j4' | grep -q cancelled"

# --- prune -------------------------------------------------------------------
refused "prune of a live job is refused" invalid_state serve_raw agent "{\"op\":\"prune\",\"job\":\"$(submit agent submit sample-long --param step_seconds=5)\"}"
check "prune removes work/" sh -c "'$REMOTE' operator prune '$j1' | grep -q 'pruned work/' && test ! -e '$ROOT/jobs/$j1/work/label'"
check "outputs survive a work prune" test -f "$ROOT/jobs/$j1/out/sample-output.txt"
check "prune --all removes the job" sh -c "'$REMOTE' operator prune '$j1' --all >/dev/null && test ! -e '$ROOT/jobs/$j1'"

# --- disable -------------------------------------------------------------------
"$W" disable >/dev/null
refused "a disabled worker refuses every key" refused serve_raw agent '{"op":"list"}'
check "disable empties authorized_keys" sh -c "! grep -v '^#' '$ROOT/.ssh/authorized_keys'"
check "disable drains the running job" sh -c "test \"\$(cat '$ROOT'/jobs/*/state | sort -u | grep -c -e draining -e paused)\" -ge 1"

echo "# $pass passed, $failed failed"
[ $failed -eq 0 ]
