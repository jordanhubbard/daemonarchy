#!/usr/bin/env bash
# The Windows programs and Steam virtual apps: first run (packages, prefix, Steam's
# installer), later launches straight into Wine or Steam, flags, failure and retry.
# Stand-ins for pkg, sudo, wine, curl and the terminal run the state machine for real.
set -euo pipefail
trap 'echo "FAILED at line $LINENO: $BASH_COMMAND" >&2' ERR
here=$(cd "$(dirname "$0")/.." && pwd)
wine_launcher=$here/overlay/usr/local/bin/daemonarchy-wine
steam_launcher=$here/overlay/usr/local/bin/daemonarchy-steam
share=$here/overlay/usr/local/share/daemonarchy-installer
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
check() { [[ $1 == "$2" ]] || { echo "Expected '$2', got '$1'" >&2; exit 1; }; }
count() { grep -c -- "$1" "$2" 2>/dev/null || true; }
never() { if "$@"; then echo "unexpected success: $*" >&2; exit 1; fi; }

mkdir -p "$work/bin"
# pkg: installed packages are marker files; install can be made to fail (offline).
cat >"$work/bin/pkg" <<'STUB'
#!/usr/bin/env bash
echo "pkg $*" >>"$PKG_LOG"
case $1 in
  info) [[ $2 == -e && -e $INSTALLED/$3 ]] ;;
  query)
    case ${3:-} in
      nvidia-kmod) [[ -n ${NO_NVIDIA_PKG:-} ]] || echo "${NVIDIA_KMOD_VER:-595.104.02.1600029}" ;;
      nvidia-drm-612-kmod) [[ -n ${NO_NVIDIA_PKG:-} ]] || echo "${NVIDIA_DRM_VER:-595.104.02.1600029_1}" ;;
      *) case $2 in %v) echo 11.20,1 ;; %n-%v) echo wine-devel-11.20,1 ;; esac ;;
    esac ;;
  install)
    [[ -z ${PKG_FAIL:-} ]] || { echo 'pkg: Fetching failed (stub: offline)' >&2; exit 1; }
    shift
    for p in "$@"; do [[ $p == -* ]] || : >"$INSTALLED/$p"; done ;;
esac
STUB
# sudo: the password prompt is the window's business; run what it was given.
cat >"$work/bin/sudo" <<'STUB'
#!/usr/bin/env bash
echo "sudo $*" >>"$PKG_LOG"
exec "$@"
STUB
# wine: record the call; make the prefix and Steam's files the way Wine would.
cat >"$work/bin/wine" <<'STUB'
#!/usr/bin/env bash
echo "wine $* | prefix=$WINEPREFIX overrides=$WINEDLLOVERRIDES" >>"$WINE_LOG"
# What the program is given for input and output, and what the first boot saw of the display.
echo "$1 stdin=$(readlink /proc/$$/fd/0) stdout=$(stat -L -c %F /proc/$$/fd/1) display=${DISPLAY:-unset}${WAYLAND_DISPLAY:-unset} arch=${WINEARCH:-unset}" >>"$WINE_LOG.io"
case $1 in
  wineboot)
    [[ -z ${WINEBOOT_FAIL:-} ]] || exit 1
    mkdir -p "$WINEPREFIX/drive_c/windows/system32" "$WINEPREFIX/drive_c/windows/syswow64"
    : >"$WINEPREFIX/system.reg" ;;
  msiexec) [[ $3 != *wine-mono* ]] || mkdir -p "$WINEPREFIX/drive_c/windows/mono" ;;
  *SteamSetup.exe) mkdir -p "$WINEPREFIX/drive_c/Program Files (x86)/Steam"; [[ -n ${STEAMSETUP_FAIL:-} ]] || : >"$WINEPREFIX/drive_c/Program Files (x86)/Steam/Steam.exe" ;;
  *steam.exe)
    [[ -z ${STEAM_STOPS:-} ]] || exit 3
    if [[ -n ${STEAM_RESTARTS:-} ]]; then   # the bootstrapper's "start me again" after an update
      n=$(cat "$WINE_LOG.n" 2>/dev/null || echo 0)
      if ((n < STEAM_RESTARTS)); then echo $((n + 1)) >"$WINE_LOG.n"; exit 42; fi
    fi ;;
esac
exit 0
STUB
# wineserver: Wine writes its registry when the server exits; -w waits for that.
cat >"$work/bin/wineserver" <<'STUB'
#!/usr/bin/env bash
echo "wineserver $* | prefix=$WINEPREFIX" >>"$WINE_LOG"
STUB
# curl: an HTTPS download of an MZ file, or a failure.
cat >"$work/bin/curl" <<'STUB'
#!/usr/bin/env bash
echo "curl $*" >>"$CURL_LOG"
[[ -z ${CURL_FAIL:-} ]] || exit 22
out= url=
while (($#)); do [[ $1 == -o ]] && out=$2; url=$1; shift; done
[[ -z ${CURL_FAIL_STEAM:-} || $url != *steamstatic* ]] || exit 22
case $url in
  *wine-mono*) { printf 'MZ'; echo mono-test; } >"$out" ;;
  *dxvk*) cp "$DXVK_TGZ" "$out" ;;
  *) { printf 'MZ'; head -c 200000 /dev/zero; } >"$out" ;;
esac
STUB
# The system tools the graphics checks ask: the loaded kernel modules, the OSVERSION, the kernel
# identity, vulkaninfo and Xwayland. Each can be made to say something else.
cat >"$work/bin/kldstat" <<'STUB'
#!/usr/bin/env bash
name=${*: -1}
name=${name%.ko}
case ",${KLD_LOADED-nvidia,nvidia-drm}," in *",$name,"*) exit 0 ;; esac
exit 1
STUB
cat >"$work/bin/sysctl" <<'STUB'
#!/usr/bin/env bash
echo 1600029
STUB
cat >"$work/bin/uname" <<'STUB'
#!/usr/bin/env bash
if [[ ${1:-} == -v ]]; then echo 'FreeBSD 16.0-CURRENT #3 303b3646270f: Thu Oct 29 23:50:00 UTC 2026'; else exec /usr/bin/uname "$@"; fi
STUB
cat >"$work/bin/vulkaninfo" <<'STUB'
#!/usr/bin/env bash
printf 'GPU0:\n\tapiVersion         = %s\n\tdeviceName         = %s\n\tdriverName         = %s\n' \
  "${VK_API:-1.4.325}" "${VK_DEVICE:-NVIDIA GeForce RTX 5080}" "${VK_DRIVER:-NVIDIA}"
STUB
printf '#!/bin/sh\n' >"$work/bin/Xwayland"
# foot: a window; run the command it is given, as the window would.
cat >"$work/bin/foot" <<'STUB'
#!/bin/sh
echo "window: $*" >>"$FOOT_LOG"
while [ $# -gt 0 ]; do case $1 in --*) shift ;; *) break ;; esac; done
exec "$@"
STUB
chmod +x "$work"/bin/*

# DXVK's release tarball (the layout of upstream's: dxvk-VERSION/x64 and x32), Wine Mono's MSI as the
# curl stub makes it, and the pins the launcher is told to expect for them.
mkdir -p "$work/dxvk/dxvk-3.1.1/x64" "$work/dxvk/dxvk-3.1.1/x32"
for dll in d3d8 d3d9 d3d10core d3d11 dxgi; do
  printf 'MZ x64 %s\n' "$dll" >"$work/dxvk/dxvk-3.1.1/x64/$dll.dll"
  printf 'MZ x32 %s\n' "$dll" >"$work/dxvk/dxvk-3.1.1/x32/$dll.dll"
done
tar -czf "$work/dxvk.tgz" -C "$work/dxvk" dxvk-3.1.1
export DXVK_TGZ=$work/dxvk.tgz
dxvk_sha=$(sha256sum "$work/dxvk.tgz" | cut -d' ' -f1)
mono_sha=$({ printf 'MZ'; echo mono-test; } | sha256sum | cut -d' ' -f1)
export DAEMONARCHY_DXVK_URL=https://example.invalid/dxvk-test.tar.gz DAEMONARCHY_DXVK_SHA256=$dxvk_sha
export DAEMONARCHY_MONO_URL=https://example.invalid/wine-mono-test.msi DAEMONARCHY_MONO_SHA256=$mono_sha

fresh() { # a new home, empty package state and logs
  rm -rf "${work:?}/home" "${work:?}/installed"
  mkdir -p "$work/home" "$work/installed"
  : >"$work/pkg.log"; : >"$work/wine.log"; : >"$work/wine.log.io"; : >"$work/curl.log"; : >"$work/foot.log"
  unset PKG_FAIL CURL_FAIL CURL_FAIL_STEAM WINEBOOT_FAIL STEAMSETUP_FAIL STEAM_STOPS DAEMONARCHY_STEAM_ARGS \
        NO_XWAYLAND KLD_LOADED NVIDIA_KMOD_VER NVIDIA_DRM_VER NO_NVIDIA_PKG VK_DRIVER VK_API VULKANINFO_BIN DAEMONARCHY_DXVK
  export DAEMONARCHY_MONO_SHA256=$mono_sha DAEMONARCHY_DXVK_SHA256=$dxvk_sha
  # shellcheck disable=SC2155
  prefix=$work/home/.local/share/daemonarchy-wine/prefix
  state=$work/home/.local/state/daemonarchy-wine
}
run() { # launcher [args]: as the desktop launches it, with no terminal
  local launcher=$1 xwayland=$work/bin/Xwayland
  shift
  [[ -z ${NO_XWAYLAND:-} ]] || xwayland=$work/bin/not-installed
  env HOME="$work/home" PATH="$work/bin:$PATH" INSTALLED="$work/installed" PKG_LOG="$work/pkg.log" \
      WINE_LOG="$work/wine.log" CURL_LOG="$work/curl.log" FOOT_LOG="$work/foot.log" \
      DAEMONARCHY_XWAYLAND="$xwayland" DAEMONARCHY_VULKANINFO="${VULKANINFO_BIN:-$work/bin/vulkaninfo}" \
      DAEMONARCHY_WINE_NO_NOTIFY=1 DAEMONARCHY_WINE_FOREGROUND=1 DAEMONARCHY_WINE_ARCH=amd64 \
      bash "$launcher" "$@" </dev/null
}
wine() { run "$wine_launcher" "$@"; }
steam() { run "$steam_launcher" "$@"; }

# --- unsupported architecture: refused before anything is installed
fresh
if env HOME="$work/home" PATH="$work/bin:$PATH" INSTALLED="$work/installed" PKG_LOG="$work/pkg.log" WINE_LOG="$work/wine.log" \
     DAEMONARCHY_WINE_NO_NOTIFY=1 DAEMONARCHY_WINE_ARCH=aarch64 bash "$wine_launcher" >"$work/out" 2>&1 </dev/null; then
  echo 'aarch64 launched Wine' >&2; exit 1
fi
grep -q 'amd64 only' "$work/out"
[[ ! -s $work/pkg.log && ! -s $work/wine.log ]]
env HOME="$work/home" PATH="$work/bin:$PATH" INSTALLED="$work/installed" PKG_LOG="$work/pkg.log" DAEMONARCHY_WINE_ARCH=aarch64 \
    bash "$wine_launcher" --status </dev/null >"$work/st"
grep -q '^unsupported: .*amd64 only' "$work/st"
echo 'PASS: refused on a non-amd64 machine, nothing installed'

# --- status before and after
fresh
grep -q '^virtual app: not set up yet (the first launch installs wine-devel wine-gecko-devel winetricks xwayland vulkan-tools' <<<"$(wine --status)"
grep -q 'Steam: not installed (daemonarchy-steam downloads it from Valve' <<<"$(wine --status)"

# --- first launch of Windows programs: a window, one sudo pkg install, the prefix, then the program
wine >"$work/out" 2>&1
check "$(count '^window:' "$work/foot.log")" 1
grep -q -- '--app-id=daemonarchy-wine-setup' "$work/foot.log"
check "$(count '^sudo env IGNORE_OSVERSION=yes ASSUME_ALWAYS_YES=yes pkg install -y wine-devel wine-gecko-devel winetricks xwayland vulkan-tools$' "$work/pkg.log")" 1
# The 64-bit prefix is made with no display and Mono and Gecko off, then the server is waited for.
grep -q "^wine wineboot -i | prefix=$prefix overrides=mscoree,mshtml=$" "$work/wine.log"
grep -q '^wineboot stdin=/dev/null stdout=.* display=unsetunset arch=win64$' "$work/wine.log.io"
grep -q "^wineserver -w | prefix=$prefix$" "$work/wine.log"         # the registry is written when the server exits
# Wine Mono from the pinned MSI, quietly; DXVK's DLLs in system32 (64-bit) and syswow64 (32-bit), set to native.
grep -q "^wine msiexec /i $work/home/.local/share/daemonarchy-wine/downloads/wine-mono-10.4.1-x86.msi /qn | prefix=$prefix " "$work/wine.log"
for dll in d3d8 d3d9 d3d10core d3d11 dxgi; do
  grep -q "^MZ x64 $dll$" "$prefix/drive_c/windows/system32/$dll.dll"
  grep -q "^MZ x32 $dll$" "$prefix/drive_c/windows/syswow64/$dll.dll"
  grep -q "^wine reg add HKCU.Software.Wine.DllOverrides /v $dll /d native /f | prefix=$prefix " "$work/wine.log"
done
grep -q "^wine winefile | prefix=$prefix " "$work/wine.log"          # no argument: Wine's file manager
[[ -f $prefix/system.reg && -f $work/home/.local/share/daemonarchy-wine/setup ]]
grep -q '^wine=11.20,1$' "$work/home/.local/share/daemonarchy-wine/setup"
grep -q '^mono=10.4.1$' "$work/home/.local/share/daemonarchy-wine/setup"
grep -q '^dxvk=3.1.1$' "$work/home/.local/share/daemonarchy-wine/setup"
never grep -q 'steamstatic' "$work/curl.log"                         # nothing of Valve's for plain Wine
check "$(count '^curl ' "$work/curl.log")" 2                          # Wine Mono's MSI and DXVK, both over HTTPS
never grep -q 'http://' "$work/curl.log"
grep -q 'ok: native Vulkan on NVIDIA' "$work/out" || grep -q 'ok: native Vulkan on NVIDIA' "$state/setup.log" || {
  # the window prints into the window's own output; the log holds the same lines
  grep -q 'graphics stack looks right' "$state/setup.log" || { cat "$state/setup.log" >&2; exit 1; }; }
wine --status >"$work/st" 2>&1; cat "$work/st" >&2; grep -q "^real app: Wine is set up (wine-devel-11.20,1)" "$work/st"
grep -q '^  Wine Mono 10.4.1; DXVK 3.1.1$' "$work/st"
echo 'PASS: first launch installs the packages once, makes the 64-bit prefix, Mono and DXVK, and opens Wine'

# --- later launches: no window, no sudo, straight to Wine; .exe and .msi are started by their types
: >"$work/foot.log"; : >"$work/pkg.log"; : >"$work/wine.log"
: >"$work/game.exe"; : >"$work/setup.MSI"
wine "$work/game.exe" -windowed
wine "$work/setup.MSI"
wine notepad
check "$(count '^window:' "$work/foot.log")" 0
check "$(count '^sudo' "$work/pkg.log")" 0
grep -q "^wine start /unix $work/game.exe -windowed | prefix=$prefix " "$work/wine.log"
grep -q "^wine msiexec /i $work/setup.MSI | prefix=$prefix " "$work/wine.log"
grep -q "^wine notepad | prefix=$prefix " "$work/wine.log"
echo 'PASS: later launches go straight to the program'

# --- from a terminal the program is detached, so the window closes
: >"$work/wine.log"
env HOME="$work/home" PATH="$work/bin:$PATH" INSTALLED="$work/installed" PKG_LOG="$work/pkg.log" WINE_LOG="$work/wine.log" \
    DAEMONARCHY_WINE_NO_NOTIFY=1 DAEMONARCHY_WINE_ARCH=amd64 DAEMONARCHY_WINE_DETACH=1 bash "$wine_launcher" winecfg </dev/null
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do grep -q '^wine winecfg' "$work/wine.log" && break; sleep 0.2; done
grep -q "^wine winecfg | prefix=$prefix " "$work/wine.log"
echo 'PASS: a detached launch returns at once and the program runs'

# --- Steam: first launch downloads Valve's installer over HTTPS, runs it, then opens Steam
fresh
steam >"$work/out" 2>&1 || { cat "$work/out" "$state/setup.log" >&2; exit 1; }
check "$(count '^window:' "$work/foot.log")" 1
check "$(count 'steamstatic' "$work/curl.log")" 1                    # Valve's installer, once, from Valve
grep -q -- '--proto =https' "$work/curl.log"
grep -q 'https://cdn.cloudflare.steamstatic.com/client/installer/SteamSetup.exe' "$work/curl.log"
never grep -q 'http://' "$work/curl.log"
grep -q "^wine $work/home/.local/share/daemonarchy-wine/downloads/SteamSetup.exe /S | prefix=$prefix " "$work/wine.log"
grep -q "^wine C:.Program Files (x86).Steam.steam.exe -no-cef-sandbox | prefix=$prefix " "$work/wine.log"
grep -q '^steam=installed$' "$work/home/.local/share/daemonarchy-wine/setup"
grep -q '^  Steam: installed in the prefix' <<<"$(wine --status)"
# the launcher ships nothing of Valve's: no Steam binary, installer or logo in the overlay
! git -C "$here" ls-files overlay | grep -i -E 'steamsetup|steam\.exe|steam_logo' >/dev/null 2>&1 || { echo 'Valve files in the overlay' >&2; exit 1; }
echo 'PASS: Steam is downloaded from Valve at the first launch, then opened'

# --- later Steam launches: no window, no download; arguments and a steam:// URL pass through
: >"$work/foot.log"; : >"$work/curl.log"; : >"$work/wine.log"
steam steam://rungameid/440
DAEMONARCHY_STEAM_ARGS='-no-cef-sandbox -cef-disable-gpu' steam
check "$(count '^window:' "$work/foot.log")" 0
check "$(count '^curl' "$work/curl.log")" 0
grep -q "steam.exe -no-cef-sandbox steam://rungameid/440 | prefix=$prefix " "$work/wine.log"
grep -q "steam.exe -no-cef-sandbox -cef-disable-gpu | prefix=$prefix " "$work/wine.log"
echo 'PASS: later Steam launches go straight to Steam'

# --- Steam's "start me again" (status 42) after its self-update is honoured, a few times at most
: >"$work/wine.log"; rm -f "$work/wine.log.n"
STEAM_RESTARTS=1 steam
check "$(count 'steam.exe -no-cef-sandbox' "$work/wine.log")" 2
grep -q 'asked to be started again after its update (1)' "$state/app.log"
: >"$work/wine.log"; rm -f "$work/wine.log.n"
if STEAM_RESTARTS=9 steam >/dev/null 2>&1; then echo 'endless restarts reported success' >&2; exit 1; fi
check "$(count 'steam.exe -no-cef-sandbox' "$work/wine.log")" 3
rm -f "$work/wine.log.n"
echo 'PASS: Steam is started again after its update, at most three times'

# --- Steam stopping with an error leaves its status in the app log
export STEAM_STOPS=1
if steam >/dev/null 2>&1; then echo 'a failing Steam reported success' >&2; exit 1; fi
unset STEAM_STOPS
grep -q '== stopped with status 3' "$state/app.log"
echo 'PASS: a program that stops with an error is logged'

# --- offline: a clear message in the window and the log, nothing recorded, and the next launch retries
fresh
export PKG_FAIL=1
if steam >"$work/out" 2>&1; then echo 'launched with no packages' >&2; exit 1; fi
grep -q 'could not be installed (is the network up?)' "$state/setup.log"
grep -q 'Press Enter to close this window; the next launch tries again.' "$work/out"
[[ ! -e $work/home/.local/share/daemonarchy-wine/setup ]]
check "$(count '^wine' "$work/wine.log")" 0
unset PKG_FAIL
export CURL_FAIL=1
if steam >"$work/out" 2>&1; then echo 'launched without Wine Mono' >&2; exit 1; fi
grep -q 'Wine Mono could not be downloaded and verified (is the network up?)' "$state/setup.log"
never grep -q '^mono=' "$work/home/.local/share/daemonarchy-wine/setup"
unset CURL_FAIL
export CURL_FAIL_STEAM=1
if steam >"$work/out" 2>&1; then echo 'launched without Steam' >&2; exit 1; fi
grep -q "Steam's installer could not be downloaded (is the network up?)" "$state/setup.log"
grep -q '^mono=10.4.1$' "$work/home/.local/share/daemonarchy-wine/setup"      # what did work is kept
never grep -q '^steam=installed' "$work/home/.local/share/daemonarchy-wine/setup"
check "$(count steam.exe "$work/wine.log")" 0
before=$(count '^curl' "$work/curl.log")
unset CURL_FAIL_STEAM
steam >"$work/out" 2>&1
grep -q '^steam=installed$' "$work/home/.local/share/daemonarchy-wine/setup"
(( $(count '^curl' "$work/curl.log") > before ))
grep -q 'steam.exe -no-cef-sandbox' "$work/wine.log"
echo 'PASS: offline failures are explained, recorded nowhere, and the next launch retries'

# --- a prefix that Wine cannot create and an installer that does not finish are reported
fresh
export WINEBOOT_FAIL=1
if wine >"$work/out" 2>&1; then echo 'launched without a prefix' >&2; exit 1; fi
grep -q 'Wine could not create its prefix' "$state/setup.log"
unset WINEBOOT_FAIL
export STEAMSETUP_FAIL=1
if steam >"$work/out" 2>&1; then echo 'launched without Steam installed' >&2; exit 1; fi
grep -q "Steam's installer did not finish" "$state/setup.log"
unset STEAMSETUP_FAIL
echo 'PASS: a failed prefix or Steam installer is reported'

# --- --setup runs no program; --rebuild forgets the record; --reset deletes the prefix
fresh
steam --setup
[[ $(grep -c . "$work/wine.log") -gt 0 ]]
never grep -q 'winefile\|steam.exe' "$work/wine.log"
grep -q '^steam=installed$' "$work/home/.local/share/daemonarchy-wine/setup"
: >"$work/wine.log"; : >"$work/curl.log"
steam --rebuild
check "$(count 'steamstatic' "$work/curl.log")" 1                    # the record is gone, so Steam is installed again
grep -q '^steam=installed$' "$work/home/.local/share/daemonarchy-wine/setup"
if steam --reset >"$work/out" 2>&1; then echo 'reset without --yes' >&2; exit 1; fi
grep -q 'Refusing to delete' "$work/out"
[[ -d $prefix ]]
grep -q 'prefix was deleted' <<<"$(steam --reset --yes)"
[[ ! -e $prefix && ! -e $work/home/.local/share/daemonarchy-wine/setup ]]
grep -q '^virtual app: not set up yet' <<<"$(wine --status)"
echo 'PASS: --setup, --rebuild and --reset'

# --- two first launches at once: one sets up, the other says so
fresh
mkdir -p "$state/lock"
echo $$ >"$state/lock/pid"
wine >"$work/out" 2>&1
grep -q 'already being set up' "$work/out"
check "$(count '^sudo' "$work/pkg.log")" 0
rm -rf "$state/lock"
echo 'PASS: a second first launch does not set up twice'

# --- the graphics checks: kernel, NVIDIA modules built for it, native Vulkan, Xwayland. Warnings, never refusals.
fresh
wine --check >"$work/out" 2>&1 || { cat "$work/out" >&2; exit 1; }
for expect in 'kernel: FreeBSD 16.0-CURRENT #3 303b3646270f' 'OSVERSION 1600029' 'ok: Xwayland is installed' \
              'ok: the nvidia kernel module is loaded' 'ok: the nvidia-drm kernel module is loaded' \
              'ok: nvidia-kmod 595.104.02.1600029 was built for this kernel' \
              'ok: nvidia-drm-612-kmod 595.104.02.1600029_1 was built for this kernel' \
              'ok: native Vulkan on NVIDIA (NVIDIA GeForce RTX 5080, Vulkan 1.4)' 'the graphics stack looks right'; do
  grep -qF -- "$expect" "$work/out" || { echo "--check lacks '$expect'" >&2; cat "$work/out" >&2; exit 1; }
done
never grep -q WARNING "$work/out"
warn_case() { # VAR=VALUE, then the warning it must produce
  # shellcheck disable=SC2163 # "$1" is NAME=VALUE: exporting it by that form is the point
  if ( export "$1"; wine --check ) >"$work/out" 2>&1; then echo "--check passed with $1" >&2; exit 1; fi
  grep -qF -- "WARNING: $2" "$work/out" || { echo "no warning '$2' with $1" >&2; cat "$work/out" >&2; exit 1; }
}
warn_case NO_XWAYLAND=1 'Xwayland is not installed'
warn_case KLD_LOADED=nvidia 'the nvidia-drm kernel module is not loaded'
warn_case KLD_LOADED=none 'the nvidia kernel module is not loaded'
warn_case NVIDIA_KMOD_VER=595.104.02.1500000 'nvidia-kmod 595.104.02.1500000 was not built for this kernel (OSVERSION 1600029)'
warn_case NO_NVIDIA_PKG=1 'nvidia-kmod is not installed'
warn_case VK_DRIVER=llvmpipe 'vulkaninfo finds no NVIDIA Vulkan device'
warn_case VK_API=1.3.280 'Vulkan 1.3: DXVK 3.1.1 needs Vulkan 1.4'
warn_case VULKANINFO_BIN="$work/bin/not-installed" 'vulkaninfo is not installed'
echo 'PASS: the graphics checks pass on a right stack and warn clearly on each wrong one'

# --- DXVK: installed when native Vulkan on NVIDIA answers, skipped (with the reason) when it does not,
# and forced or refused by DAEMONARCHY_DXVK
fresh
export VK_DRIVER=llvmpipe
wine >"$work/out" 2>&1
grep -q 'WARNING: vulkaninfo finds no NVIDIA Vulkan device' "$state/setup.log"
grep -q 'DXVK skipped: no native Vulkan on NVIDIA' "$state/setup.log"
grep -q '^dxvk=skipped$' "$work/home/.local/share/daemonarchy-wine/setup"
never grep -q 'reg add' "$work/wine.log"
[[ ! -e $prefix/drive_c/windows/system32/d3d11.dll ]]
check "$(count '^curl ' "$work/curl.log")" 1                          # only Wine Mono
grep -q 'DXVK skipped' <<<"$(wine --status)"
DAEMONARCHY_DXVK=yes wine --rebuild
grep -q '^dxvk=3.1.1$' "$work/home/.local/share/daemonarchy-wine/setup"
[[ -f $prefix/drive_c/windows/system32/d3d11.dll ]]
fresh
DAEMONARCHY_DXVK=no wine >"$work/out" 2>&1
grep -q '^dxvk=skipped$' "$work/home/.local/share/daemonarchy-wine/setup"
grep -q 'DXVK skipped (DAEMONARCHY_DXVK=no)' "$state/setup.log"
echo 'PASS: DXVK follows native Vulkan, and DAEMONARCHY_DXVK=yes or no overrides it'

# --- Wine Mono and DXVK are installed only if their sha256 is the pinned one
fresh
export DAEMONARCHY_MONO_SHA256=0000000000000000000000000000000000000000000000000000000000000000
if wine >"$work/out" 2>&1; then echo 'launched with a Mono MSI that is not the pinned one' >&2; exit 1; fi
grep -q "not the pinned 0000" "$state/setup.log" || { cat "$state/setup.log" >&2; exit 1; }
never grep -q 'msiexec' "$work/wine.log"
[[ ! -e $work/home/.local/share/daemonarchy-wine/downloads/wine-mono-10.4.1-x86.msi ]]
fresh
export DAEMONARCHY_DXVK_SHA256=0000000000000000000000000000000000000000000000000000000000000000
if wine >"$work/out" 2>&1; then echo 'launched with a DXVK archive that is not the pinned one' >&2; cat "$state/setup.log" >&2; exit 1; fi
grep -q 'DXVK could not be downloaded and verified' "$state/setup.log"
[[ ! -e $prefix/drive_c/windows/system32/d3d11.dll ]]
never grep -q '^dxvk=' "$work/home/.local/share/daemonarchy-wine/setup"
echo 'PASS: a download whose sha256 is not the pinned one is refused'

# --- install and run: any Windows program the user supplies; output to a log file, input from /dev/null
fresh
: >"$work/Setup.exe"; : >"$work/Launcher.exe"; : >"$work/my game.exe"; : >"$work/tool.msi"
wine install "$work/Setup.exe" /S >"$work/out" 2>&1 || { cat "$work/out" "$state/setup.log" >&2; exit 1; }
grep -q "^wine $work/Setup.exe /S | prefix=$prefix " "$work/wine.log"
grep -q 'The installer finished (status 0)' "$work/out"
grep -q "^== .*: install $work/Setup.exe /S" "$state/programs/Setup.exe.log"
grep -q "^$work/Setup.exe stdin=/dev/null stdout=regular file " "$work/wine.log.io"
wine install "$work/tool.msi" /passive >/dev/null 2>&1
grep -q "^wine msiexec /i $work/tool.msi /passive | prefix=$prefix " "$work/wine.log"
: >"$work/wine.log"; : >"$work/wine.log.io"
wine run "$work/Launcher.exe" --no-sandbox -x
grep -q "^wine $work/Launcher.exe --no-sandbox -x | prefix=$prefix " "$work/wine.log"      # arguments pass through unchanged
grep -q "^$work/Launcher.exe stdin=/dev/null stdout=regular file " "$work/wine.log.io"
grep -q "^== .*: run $work/Launcher.exe --no-sandbox -x" "$state/programs/Launcher.exe.log"
wine run "$work/my game.exe"
[[ -f "$state/programs/my_game.exe.log" ]]                                               # an awkward name gets a safe log name
wine run 'C:\Program Files\Some Game\game.exe' -windowed
grep -q "^wine C:.Program Files.Some Game.game.exe -windowed | prefix=$prefix " "$work/wine.log"     # a path inside the prefix
# the launcher's own output may be a pipe (a terminal pipeline, or the first-run window): the program's never is
: >"$work/wine.log.io"
wine run "$work/Launcher.exe" | cat >/dev/null
grep -q "^$work/Launcher.exe stdin=/dev/null stdout=regular file " "$work/wine.log.io"
never grep -q 'fifo' "$work/wine.log.io"
if wine run >"$work/out" 2>&1; then echo 'run without a program succeeded' >&2; exit 1; fi
grep -q '^usage: daemonarchy-wine run PROGRAM.exe' "$work/out"
echo 'PASS: install and run take any program, pass its arguments through, and log to a file with stdin from /dev/null'

# --- desktop entries, icons and menu entries
for name in daemonarchy-wine daemonarchy-steam; do
  [[ -f $share/$name.desktop && -f $share/$name.svg ]]
  grep -q "^Icon=$name$" "$share/$name.desktop"
  grep -q "^Exec=$name " "$share/$name.desktop"
  grep -q '^Terminal=false$' "$share/$name.desktop"
  grep -q '<svg' "$share/$name.svg"
  never grep -q -i 'script\|href\|onload' "$share/$name.svg"
  if command -v desktop-file-validate >/dev/null 2>&1; then desktop-file-validate "$share/$name.desktop"; fi
done
grep -q '^Categories=Game;$' "$share/daemonarchy-steam.desktop"
grep -q 'x-scheme-handler/steam' "$share/daemonarchy-steam.desktop"
grep -q '"system.freebsd.steam": .*uwsm-app -- daemonarchy-steam' "$share/omarchy-menu.jsonc"
grep -q '"system.freebsd.wine": .*uwsm-app -- daemonarchy-wine' "$share/omarchy-menu.jsonc"
[[ -x $wine_launcher && -x $steam_launcher ]]
bash -n "$wine_launcher"
bash -n "$steam_launcher"
echo 'PASS: desktop entries, icons and menu entries'
echo 'Windows launcher checks passed'
