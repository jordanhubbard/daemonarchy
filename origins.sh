# Ports whose packages Daemonarchy publishes itself rather than taking from
# pkg.FreeBSD.org: the Omarchy ports, and ports carrying fixes the official
# packages lack yet (x11/quickshell). Sourced by build-iso.sh and pkg-repo.sh.
OMARCHY_ORIGINS="
audio/cliamp devel/tobi-try devel/usage editors/omarchy-nvim editors/omawrite
graphics/omasnap graphics/tensaku math/omacalc misc/ttfx multimedia/omacut
sysutils/herdr sysutils/lazydocker sysutils/tzupdate sysutils/udiskie
x11-fonts/ia-writer-fonts x11-themes/aether x11-wm/omarchy
x11-wm/daemonarchy x11/hyprland-preview-share-picker x11/owe
x11/owe-lockfeed x11/quickshell
"

# The ISO also carries kernel modules built for its own kernel. They stay off
# the online repository, which installed systems on older kernels also use.
ISO_ORIGINS="$OMARCHY_ORIGINS
graphics/drm-66-kmod graphics/gpu-firmware-kmod net/wifi-firmware-kmod
"
