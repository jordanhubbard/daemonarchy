#!/bin/sh
# I allocate only a fresh private directory; I never reuse or delete prior runs.
iso_stage_create() (
    parent=${ISO_STAGE_PARENT:-/var/tmp}
    case "$parent" in
        /*) ;;
        *) echo 'ISO_STAGE_PARENT must be an absolute existing directory' >&2; exit 1 ;;
    esac
    [ -d "$parent" ] && [ ! -L "$parent" ] || {
        echo 'ISO_STAGE_PARENT must be an existing nonsymlink directory' >&2
        exit 1
    }
    umask 077
    mktemp -d "$parent/daemonarchy-iso-stage.XXXXXXXX"
)

# Repeated authoring must retain previous images, checksums and failed products.
iso_stage_require_fresh_outputs() {
    for candidate in "$@"; do
        if [ -e "$candidate" ] || [ -L "$candidate" ]; then
            echo "Preserve existing image evidence: $candidate; use a fresh output directory" >&2
            return 1
        fi
    done
}
