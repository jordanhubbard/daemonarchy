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
  query) case $2 in %v) echo 11.20,1 ;; %n-%v) echo wine-devel-11.20,1 ;; esac ;;
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
case $1 in
  wineboot) [[ -z ${WINEBOOT_FAIL:-} ]] || exit 1; mkdir -p "$WINEPREFIX/drive_c/windows"; : >"$WINEPREFIX/system.reg" ;;
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
out=
while (($#)); do [[ $1 == -o ]] && out=$2; shift; done
{ printf 'MZ'; head -c 200000 /dev/zero; } >"$out"
STUB
# foot: a window; run the command it is given, as the window would.
cat >"$work/bin/foot" <<'STUB'
#!/bin/sh
echo "window: $*" >>"$FOOT_LOG"
while [ $# -gt 0 ]; do case $1 in --*) shift ;; *) break ;; esac; done
exec "$@"
STUB
chmod +x "$work"/bin/*

fresh() { # a new home, empty package state and logs
  rm -rf "${work:?}/home" "${work:?}/installed"
  mkdir -p "$work/home" "$work/installed"
  : >"$work/pkg.log"; : >"$work/wine.log"; : >"$work/curl.log"; : >"$work/foot.log"
  unset PKG_FAIL CURL_FAIL WINEBOOT_FAIL STEAMSETUP_FAIL STEAM_STOPS DAEMONARCHY_STEAM_ARGS
  # shellcheck disable=SC2155
  prefix=$work/home/.local/share/daemonarchy-wine/prefix
  state=$work/home/.local/state/daemonarchy-wine
}
run() { # launcher [args]: as the desktop launches it, with no terminal
  local launcher=$1
  shift
  env HOME="$work/home" PATH="$work/bin:$PATH" INSTALLED="$work/installed" PKG_LOG="$work/pkg.log" \
      WINE_LOG="$work/wine.log" CURL_LOG="$work/curl.log" FOOT_LOG="$work/foot.log" \
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
grep -q '^virtual app: not set up yet (the first launch installs wine-devel wine-mono-devel wine-gecko-devel winetricks' <<<"$(wine --status)"
grep -q 'Steam: not installed (daemonarchy-steam downloads it from Valve' <<<"$(wine --status)"

# --- first launch of Windows programs: a window, one sudo pkg install, the prefix, then the program
wine >"$work/out" 2>&1
check "$(count '^window:' "$work/foot.log")" 1
grep -q -- '--app-id=daemonarchy-wine-setup' "$work/foot.log"
check "$(count '^sudo env IGNORE_OSVERSION=yes ASSUME_ALWAYS_YES=yes pkg install -y wine-devel wine-mono-devel wine-gecko-devel winetricks$' "$work/pkg.log")" 1
grep -q "^wine wineboot --init | prefix=$prefix overrides=winemenubuilder.exe=d$" "$work/wine.log"
grep -q "^wineserver -w | prefix=$prefix$" "$work/wine.log"         # the registry is written when the server exits
grep -q "^wine winefile | prefix=$prefix " "$work/wine.log"          # no argument: Wine's file manager
[[ -f $prefix/system.reg && -f $work/home/.local/share/daemonarchy-wine/setup ]]
grep -q '^wine=11.20,1$' "$work/home/.local/share/daemonarchy-wine/setup"
check "$(count curl "$work/curl.log")" 0                              # nothing of Valve's for plain Wine
wine --status >"$work/st" 2>&1; cat "$work/st" >&2; grep -q "^real app: Wine is set up (wine-devel-11.20,1)" "$work/st"
echo 'PASS: first launch installs the packages once, makes the prefix and opens Wine'

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
check "$(count '^curl ' "$work/curl.log")" 1
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
if steam >"$work/out" 2>&1; then echo 'launched without Steam' >&2; exit 1; fi
grep -q "Steam's installer could not be downloaded (is the network up?)" "$state/setup.log"
never grep -q '^steam=installed' "$work/home/.local/share/daemonarchy-wine/setup"
check "$(count steam.exe "$work/wine.log")" 0
before=$(count '^curl' "$work/curl.log")
unset CURL_FAIL
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
check "$(count '^curl' "$work/curl.log")" 1                    # the record is gone, so Steam is installed again
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
