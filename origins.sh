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
archivers/7-zip
graphics/drm-612-kmod graphics/gpu-firmware-kmod net/wifi-firmware-kmod
net/if_brcmfmac-kmod
x11/nvidia-driver x11/nvidia-kmod graphics/nvidia-drm-612-kmod x11/linux-nvidia-libs
"

# Kernel and driver ports above that are amd64-only (ONLY_FOR_ARCHS=amd64:
# DRM KMS, NVIDIA and the Apple T2 BCM4364 driver). An aarch64 bulk list and
# image omit them; see docs/aarch64.md.
ISO_ORIGINS_AMD64_ONLY="
graphics/drm-612-kmod net/if_brcmfmac-kmod
x11/nvidia-driver x11/nvidia-kmod graphics/nvidia-drm-612-kmod x11/linux-nvidia-libs
"
