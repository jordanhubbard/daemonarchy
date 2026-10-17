#!/usr/bin/env python3
"""Build the development policy kernel and verified EFI loader on FreeBSD.

Requires only public certificates. Never installs a kernel or signs an image.
The separate source worktree and logs are retained for review after a failure.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time

BASE = "bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf"
OPTIONS = [
    "WITH_BEARSSL=yes", "WITH_LOADER_VERIEXEC=yes",
    "WITH_LOADER_EFI_SECUREBOOT=yes", "WITHOUT_LOADER_VERIEXEC_VECTX=yes",
    "WITH_LOADER_VERIEXEC_PASS_MANIFEST=yes", "WITHOUT_LOADER_BIOS=yes",
    "WITHOUT_LOADER_VERIEXEC_TESTING=yes", "VE_SELF_TESTS=yes",
]


def output(*command):
    return subprocess.check_output(command, text=True).strip()


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(args):
    if platform.system() != "FreeBSD" or platform.machine() != "amd64":
        raise ValueError("Run on a qualified native FreeBSD amd64 build worker")
    source = args.source.resolve(strict=True)
    out = args.out.resolve()
    if out.is_relative_to(source):
        raise ValueError("Output must be outside the selected system source tree")
    if out.exists():
        raise ValueError("Use a fresh output directory; retained build evidence is preserved")
    if output("git", "-C", str(source), "rev-parse", "HEAD") != BASE:
        raise ValueError("Source HEAD does not match the qualified snapshot")
    subprocess.run(["git", "-C", str(source), "diff", "--quiet", "HEAD"], check=True)
    certs = [args.certificate.resolve(strict=True),
             args.selftest_certificate.resolve(strict=True)]
    for cert in certs:
        if b"PRIVATE KEY" in cert.read_bytes():
            raise ValueError("Build inputs must contain public certificates only")
    subprocess.run(["openssl", "verify", "-CAfile", str(certs[0]), str(certs[1])],
                   check=True)
    patch = Path(__file__).resolve().parent / "patches/module-policy.patch"
    loader_patch = patch.parent / "loader-rootpool.patch"
    optional_patch = patch.parent / "efi-optional-verification.patch"
    cd9660_patch = patch.parent / "cd9660-verification.patch"
    patches = (patch, loader_patch, optional_patch, cd9660_patch)
    for candidate in patches:
        subprocess.run(["git", "apply", "--numstat", str(candidate)],
                       check=True, stdout=subprocess.DEVNULL)
    out.mkdir(parents=True)
    worktree = args.prepared_source.resolve(strict=True) if args.prepared_source else out / "source"
    if args.prepared_source is None:
        subprocess.run(["git", "-C", str(source), "worktree", "add", "--detach",
                        str(worktree), BASE], check=True)
        for candidate in patches:
            subprocess.run(["git", "-C", str(worktree), "apply", "--check", str(candidate)], check=True)
            subprocess.run(["git", "-C", str(worktree), "apply", str(candidate)], check=True)
    # A retained prepared worktree may save a checkout on a build retry, but it
    # must match the exact pinned base plus these patches, with no extra edits.
    if output("git", "-C", str(worktree), "rev-parse", "HEAD") != BASE:
        raise ValueError("Prepared source HEAD differs from the qualified snapshot")
    with tempfile.TemporaryDirectory(prefix="daemonarchy-source-index-") as temporary:
        index_env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / "index"))
        subprocess.run(["git", "-C", str(worktree), "read-tree", BASE], env=index_env, check=True)
        for candidate in patches:
            subprocess.run(["git", "-C", str(worktree), "apply", "--cached", str(candidate)],
                           env=index_env, check=True)
        subprocess.run(["git", "-C", str(worktree), "diff", "--quiet"], env=index_env, check=True)
    if output("git", "-C", str(worktree), "ls-files", "--others", "--exclude-standard"):
        raise ValueError("Prepared source contains untracked files")
    subprocess.run(["git", "-C", str(worktree), "diff", "--check"], check=True)
    conf = out / "conf"
    conf.mkdir()
    config = conf / "DAEMONARCHY_SECUREBOOT"
    config.write_text(
        f'include "{worktree}/sys/amd64/conf/GENERIC"\n'
        'ident DAEMONARCHY_SECUREBOOT\n'
        'options MAC_VERIEXEC\noptions MAC_VERIEXEC_SHA256\n'
        'options DAEMONARCHY_MODULE_POLICY\ndevice mac_veriexec_parser\n')
    public = out / "public"
    public.mkdir()
    ta, vc = public / "ta_sig.pem", public / "vc_sig.pem"
    shutil.copyfile(certs[0], ta)
    shutil.copyfile(certs[1], vc)
    epoch = args.epoch if args.epoch is not None else int(time.time())
    env = dict(os.environ, SOURCE_DATE_EPOCH=str(epoch), USER="daemonarchy",
               HOSTNAME="daemonarchy-builder")

    def make(log, objdir, directory, *options):
        build_env = dict(env, MAKEOBJDIRPREFIX=str(objdir))
        with (out / log).open("w") as stream:
            subprocess.run(["make", "-C", str(directory), f"-j{args.jobs}", *options],
                           env=build_env, stdout=stream, stderr=subprocess.STDOUT,
                           check=True)

    kernel_obj, loader_obj = out / "kernel-obj", out / "loader-obj"
    print("Building the policy kernel; see kernel-build.log", flush=True)
    make("kernel-build.log", kernel_obj, worktree, "buildkernel",
         "KERNCONF=DAEMONARCHY_SECUREBOOT", f"KERNCONFDIR={conf}", "MODULES_OVERRIDE=")
    print("Building the verified EFI loader; see loader-build.log", flush=True)
    make("loader-build.log", loader_obj, worktree / "stand", *OPTIONS,
         f"TRUST_ANCHORS={ta}", f"TA_PEM_LIST={ta}", f"VC_PEM_LIST={vc}")
    if "-DLOADER_VERIEXEC_TESTING" in (out / "loader-build.log").read_text():
        raise ValueError("Loader build enabled permissive verification testing mode")
    obj_suffix = Path(str(worktree).lstrip("/")) / "amd64.amd64"
    shutil.copyfile(kernel_obj / obj_suffix / "sys/DAEMONARCHY_SECUREBOOT/kernel",
                    out / "kernel")
    shutil.copyfile(loader_obj / obj_suffix / "stand/efi/loader_lua/loader_lua.efi",
                    out / "loader_lua.efi")
    print("Building the normal EFI loader with the same boot-pool selector", flush=True)
    normal_obj = out / "normal-loader-obj"
    make("normal-loader-build.log", normal_obj, worktree / "stand",
         "WITHOUT_BEARSSL=yes", "WITHOUT_LOADER_VERIEXEC=yes",
         "WITHOUT_LOADER_EFI_SECUREBOOT=yes", "WITHOUT_LOADER_VERIEXEC_PASS_MANIFEST=yes",
         "WITHOUT_LOADER_VERIEXEC_VECTX=yes", "WITHOUT_LOADER_BIOS=yes")
    shutil.copyfile(normal_obj / obj_suffix / "stand/efi/loader_lua/loader_lua.efi",
                    out / "loader_normal.efi")
    receipt = dict(schema=1, base_source=BASE, source_patch_sha256=sha(patch),
                   loader_patch_sha256=sha(loader_patch),
                   optional_verification_patch_sha256=sha(optional_patch),
                   cd9660_patch_sha256=sha(cd9660_patch),
                   recipe_sha256=sha(Path(__file__).resolve()), build_epoch=epoch,
                   kernel_config_sha256=sha(config), loader_options=OPTIONS,
                   trust_anchor_sha256=sha(ta), selftest_certificate_sha256=sha(vc),
                   kernel_sha256=sha(out / "kernel"),
                   unsigned_loader_sha256=sha(out / "loader_lua.efi"),
                   normal_loader_sha256=sha(out / "loader_normal.efi"),
                   boot_pool_selector=1,
                   native_boot_qualified=False)
    (out / "build.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("Build complete. Signing and native firmware/kernel qualification remain required.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--prepared-source", type=Path,
                        help="reuse a worktree containing exactly the pinned base plus current patches")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--certificate", type=Path, required=True)
    parser.add_argument("--selftest-certificate", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--epoch", type=int)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 32 or (args.epoch is not None and args.epoch <= 0):
        parser.error("Use 1..32 build jobs and a positive build epoch")
    try:
        build(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Build failed: {error}\n")
