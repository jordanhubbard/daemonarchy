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
