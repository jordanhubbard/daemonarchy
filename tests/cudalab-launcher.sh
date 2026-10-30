#!/usr/bin/env bash
# The Cudalab virtual app: build once, become the real app, chain-launch it.
# A fake Linux root stands in for the Linuxulator: its bash records the commands the
# launcher gives it and "builds" a stub executable, so the state machine runs for real.
set -euo pipefail
trap 'echo "FAILED at line $LINENO: $BASH_COMMAND" >&2' ERR
here=$(cd "$(dirname "$0")/.." && pwd)
launcher=$here/overlay/usr/local/bin/daemonarchy-cudalab
pin=cba96454837ceac1c4fbbd6ba574d56da30eadbd
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
check() { [[ $1 == "$2" ]] || { echo "Expected '$2', got '$1'" >&2; exit 1; }; }
count() { grep -c -- "$1" "$2" 2>/dev/null || true; }

# --- the fake Linux root
linux=$work/linux
mkdir -p "$linux/bin" "$linux/usr/local/lib/daemonarchy"
ln -s /etc/alternatives/cuda "$linux/usr/local/cuda"   # dangles from the FreeBSD side, as on the MSI
: >"$linux/usr/local/lib/daemonarchy/dummy-uvm.so"
cat >"$linux/bin/bash" <<'STUB'
#!/usr/bin/env bash
# Stand-in for the Linux bash: record the command, fake what it would have built.
cmd=$2
echo "$cmd" >>"$LX_LOG"
case $cmd in
  *"test -x /usr/local/cuda/bin/nvcc"*) [[ -z ${LX_NO_CUDA:-} ]] ;;
  *"git status --porcelain"*) [[ -z ${LX_DIRTY:-} ]] || echo ' M examples/cosmos.cu' ;;
  *"git clone"*) mkdir -p src/.git src/examples; : >src/CMakePresets.json ;;
  *"git checkout"*) : ;;
  *curl*) mkdir -p SDL-3.2 ;;
  *"cmake --preset release"*) mkdir -p build/release ;;
  *"cmake --build"*)
    sleep "${LX_BUILD_SLEEP:-0}"
    [[ -z ${LX_FAIL_BUILD:-} ]] || { echo 'nvcc fatal: stub build failure' >&2; exit 1; }
    mkdir -p build/release/examples
    printf '#!/bin/sh\necho "args=$* preload=${LD_PRELOAD:-} audio=${SDL_AUDIODRIVER:-} video=${SDL_VIDEODRIVER:-} cwd=$(pwd)" >> "%s"\n' "$APP_OUT" >build/release/cudalab
    chmod +x build/release/cudalab ;;
esac
STUB
chmod +x "$linux/bin/bash"

# --- a stand-in terminal: run the command it is given, as a window would
mkdir -p "$work/bin"
cat >"$work/bin/footstub" <<'STUB'
#!/bin/sh
echo "window: $*" >>"$FOOT_LOG"
while [ $# -gt 0 ]; do case $1 in --*) shift ;; *) break ;; esac; done
exec "$@"
STUB
chmod +x "$work/bin/footstub"

fresh() {   # a new user home and fresh logs
  rm -rf "$work/home" "$work/lx.log" "$work/app.out" "$work/foot.log"
  mkdir -p "$work/home"
  : >"$work/lx.log"; : >"$work/app.out"; : >"$work/foot.log"
}
run() {     # run LAUNCHER ARGS... in the fake environment (stdout is not a terminal)
  HOME=$work/home DAEMONARCHY_LINUX_ROOT=$linux CUDALAB_NO_NOTIFY=1 DISPLAY=:0 \
    LX_LOG=$work/lx.log APP_OUT=$work/app.out FOOT_LOG=$work/foot.log CUDALAB_TERMINAL=${TERM_STUB:-$work/bin/footstub} \
    bash "$launcher" "$@" </dev/null
}
stamp=$work/home/.local/share/cudalab/built

# --- the pin is a full commit, and the old behaviour is gone
[[ $pin =~ ^[0-9a-f]{40}$ ]]
grep -q "^cl_commit=$pin\$" "$launcher"
! grep -n 'rm -rf build' "$launcher"
! grep -nE '^[^#]*(sudo -|exec sudo|chroot |mount -t)' "$launcher"
grep -q 'SDL_AUDIODRIVER:-dummy' "$launcher"

# --- virtual before the first launch
fresh
[[ $(run --status) == virtual* ]]

# --- first launch: opens a window, builds once, becomes the real app, chain-launches it
run cuda-cosmos
[[ -f $stamp ]]
grep -qx "commit=$pin" "$stamp"
[[ $(run --status) == real* ]]
check "$(count 'window: ' "$work/foot.log")" 1
grep -q 'Building Cudalab (first run only)' "$work/foot.log"
check "$(count 'git clone' "$work/lx.log")" 1
grep -q "git checkout --quiet --detach '$pin'" "$work/lx.log"
grep -q "cmake --preset release -DBUILD_TESTING=OFF -DFETCHCONTENT_SOURCE_DIR_SDL3=" "$work/lx.log"
check "$(count 'cmake --build --preset release' "$work/lx.log")" 1
check "$(wc -l <"$work/app.out" | tr -d ' ')" 1
grep -q 'args=--demo cuda-cosmos ' "$work/app.out"
grep -q 'audio=dummy' "$work/app.out"
grep -q 'video=x11' "$work/app.out"
grep -q 'preload=/usr/local/lib/daemonarchy/dummy-uvm.so' "$work/app.out"
grep -q 'cwd=.*/cudalab/src' "$work/app.out"
grep -q '==> Checking out Cudalab' "$work/home/.local/state/cudalab/build.log"

# --- second launch: straight to the app, nothing is built and no window opens
before=$(wc -l <"$work/lx.log")
run
check "$(wc -l <"$work/lx.log" | tr -d ' ')" "$before"
check "$(count 'window: ' "$work/foot.log")" 1
check "$(wc -l <"$work/app.out" | tr -d ' ')" 2
grep -q 'args= ' <(sed -n 2p "$work/app.out")

# --- a stamp for another revision is not the real app: it builds again
sed -i 's/^commit=.*/commit=0000000000000000000000000000000000000000/' "$stamp"
[[ $(run --status) == virtual* ]]
run --build-only
grep -qx "commit=$pin" "$stamp"

# --- --rebuild forgets the build and builds again
before=$(count 'cmake --build' "$work/lx.log")
run --rebuild
check "$(count 'cmake --build' "$work/lx.log")" "$((before + 1))"

# --- failure is not fatal: it stays virtual, says why, and a retry works
fresh
if LX_FAIL_BUILD=1 run cuda-cosmos; then echo 'a failed build reported success' >&2; exit 1; fi
[[ ! -f $stamp ]]
[[ ! -s $work/app.out ]]
[[ $(run --status) == virtual* ]]
grep -q 'the build failed' "$work/home/.local/state/cudalab/build.log"
grep -q 'stub build failure' "$work/home/.local/state/cudalab/build.log" || true
run cuda-cosmos
[[ -f $stamp ]]
check "$(wc -l <"$work/app.out" | tr -d ' ')" 1

# --- no terminal program: the build is quiet, the app still opens
fresh
TERM_STUB=no-such-terminal run
[[ -f $stamp ]]
check "$(wc -l <"$work/app.out" | tr -d ' ')" 1
[[ ! -s $work/foot.log ]]

# --- two launches at once build once
fresh
LX_BUILD_SLEEP=2 TERM_STUB=no-such-terminal run cuda-cosmos &
first=$!
sleep 1
if ! second=$(TERM_STUB=no-such-terminal run cuda-cosmos 2>&1); then echo 'the second launch failed' >&2; exit 1; fi
grep -q 'already being built' <<<"$second"
wait "$first"
check "$(count 'git clone' "$work/lx.log")" 1
check "$(count 'cmake --build' "$work/lx.log")" 1
check "$(wc -l <"$work/app.out" | tr -d ' ')" 1
[[ ! -d $work/home/.local/state/cudalab/lock ]]

# --- a lock left by a dead launcher does not block forever
fresh
mkdir -p "$work/home/.local/state/cudalab/lock"
echo 999999 >"$work/home/.local/state/cudalab/lock/pid"
TERM_STUB=no-such-terminal run
[[ -f $stamp ]]

# --- the installer's CUDA phase built it already: the first boot opens the real app
fresh
run --build-only
[[ -f $stamp ]]
[[ ! -s $work/app.out ]]
before=$(wc -l <"$work/lx.log")
run cuda-cosmos
check "$(wc -l <"$work/lx.log" | tr -d ' ')" "$before"
[[ ! -s $work/foot.log ]]
check "$(wc -l <"$work/app.out" | tr -d ' ')" 1
run --build-only | grep -q 'already built'

# --- local edits to the sources are kept, not overwritten by the pinned checkout
fresh
run --build-only
: >"$work/lx.log"
rm -f "$stamp"
LX_DIRTY=1 run --build-only
! grep -q 'git checkout' "$work/lx.log"
[[ -f $stamp ]]

# --- no CUDA toolkit: say how to get it, build nothing
fresh
if LX_NO_CUDA=1 run --build-only 2>/dev/null; then echo 'built without a CUDA toolkit' >&2; exit 1; fi
grep -q 'daemonarchy-linux-cuda setup' "$work/home/.local/state/cudalab/build.log"
[[ ! -f $stamp ]]
! grep -q 'git clone' "$work/lx.log"

echo 'PASS: Cudalab virtual app builds once, becomes the real app and chain-launches it'
