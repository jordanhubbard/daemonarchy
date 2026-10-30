#!/usr/bin/env python3
"""daemonarchy-gpu-report on the MSI Raider's real eglinfo/glxinfo/nvidia-smi output (hybrid Intel + NVIDIA)."""

import importlib.machinery
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "overlay/usr/local/bin/daemonarchy-gpu-report"
FIXTURES = ROOT / "tests/fixtures/gpu-report"
loader = importlib.machinery.SourceFileLoader("gpu_report", str(TOOL))
spec = importlib.util.spec_from_loader(loader.name, loader)
tool = importlib.util.module_from_spec(spec)
loader.exec_module(tool)

NAMES = {"msi-pciconf.txt": "pciconf.txt", "msi-eglinfo-default.txt": "eglinfo-default.txt",
         "msi-eglinfo-wayland.txt": "eglinfo-wayland.txt", "msi-glxinfo.txt": "glxinfo.txt",
         "msi-nvidia-smi.csv": "nvidia-smi.csv"}


def staged(tmp, drop=(), **replace):
    """A --from directory of the MSI captures; `replace` maps a saved name to new text."""
    for source, name in NAMES.items():
        if name in drop:
            continue
        text = replace.get(name.rsplit(".", 1)[0].replace("-", "_"))
        (tmp / name).write_text(text if text is not None else (FIXTURES / source).read_text())
    (tmp / "kldstat.txt").write_text(" 34    1 0xffffffff83800000   251420 i915kms.ko\n 35    3 0xffffffff83a52000    a6430 drm.ko\n"
                                     " 42    2 0xffffffff83c00000  5b7b838 nvidia.ko\n 41    1 0xffffffff83b06000    15a30 nvidia-drm.ko\n")
    return tmp


class Classification(unittest.TestCase):
    def test_software_virtual_and_hardware_renderers(self):
        for renderer, kind in (("llvmpipe (LLVM 19.1.7, 256 bits)", "software"), ("softpipe", "software"),
                               ("zink Vulkan 1.3 (llvmpipe)", "software"), ("virgl (NVIDIA GeForce RTX 5080)", "virtual"),
                               ("SVGA3D; build: RELEASE", "virtual"), ("Mesa Intel(R) Graphics (ARL)", "hardware"),
                               ("NVIDIA GeForce RTX 5080 Laptop GPU/PCIe/SSE2", "hardware"), ("AMD Radeon Pro 5500M", "hardware"),
                               (None, "unknown")):
            self.assertEqual(tool.classify(renderer), kind, renderer)


class MsiHybrid(unittest.TestCase):
    def report(self, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            return tool.build_report(tool.collect_saved(staged(Path(tmp), **kw)))

    def test_both_pci_gpus_and_the_modules_are_listed(self):
        report = self.report()
        self.assertTrue(report["hybrid"])
        self.assertEqual([(g["vendor"], g["device_id"]) for g in report["gpus"]], [("Intel", "0x7d67"), ("NVIDIA", "0x2c19")])
        self.assertEqual(report["drivers"], ["drm", "i915kms", "nvidia", "nvidia-drm"])
        self.assertEqual(report["nvidia_smi"][0]["driver"], "595.104.02")

    def test_egl_devices_include_a_software_device_that_is_not_the_session(self):
        report = self.report()
        classes = {d["platform"]: (d["vendor"], d["class"]) for d in report["egl_devices"]}
        self.assertEqual(classes["Device #0"], ("NVIDIA", "hardware"))
        self.assertEqual(classes["Device #1"], ("Intel", "hardware"))
        self.assertEqual(classes["Device #3"][1], "software")
        self.assertTrue(report["software_devices_present"])
        self.assertEqual(report["verdict"], "accelerated")

    def test_the_session_is_matched_to_the_gpu_it_runs_on(self):
        session = self.report()["session"]
        self.assertEqual(session["via"], "wayland")
        self.assertIn("Intel(R) Graphics (ARL)", session["renderer"])
        self.assertEqual((session["vendor"], session["classification"], session["pci"]), ("Intel", "hardware", "vgapci0@pci0:0:2:0"))
        self.assertTrue(session["api_version"].startswith("4.6"))

    def test_x11_is_used_when_there_is_no_wayland_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = staged(Path(tmp), drop=("eglinfo-wayland.txt",))
            report = tool.build_report(tool.collect_saved(directory))
        self.assertEqual(report["session"]["via"], "x11")
        self.assertEqual(report["verdict"], "accelerated")

    def test_software_rendering_is_a_fallback_not_acceleration(self):
        # The session's own view reports llvmpipe: the Wayland capture with its renderer lines replaced.
        wayland = (FIXTURES / "msi-eglinfo-wayland.txt").read_text().replace("Mesa Intel(R) Graphics (ARL)", "llvmpipe (LLVM 19.1.7, 256 bits)")
        wayland = wayland.replace("OpenGL core profile vendor: Intel", "OpenGL core profile vendor: Mesa")
        with tempfile.TemporaryDirectory() as tmp:
            directory = staged(Path(tmp), eglinfo_wayland=wayland)
            report = tool.build_report(tool.collect_saved(directory))
        self.assertEqual(report["session"]["classification"], "software")
        self.assertEqual(report["verdict"], "software-fallback")
        self.assertIn("never counts as acceleration", tool.render(report))

    def test_nothing_to_report_is_unknown(self):
        report = tool.build_report({})
        self.assertEqual((report["verdict"], report["session"], report["gpus"]), ("unknown", None, []))


class CommandLine(unittest.TestCase):
    def run_tool(self, *args, **kw):
        return subprocess.run([sys.executable, "-I", str(TOOL), *args], capture_output=True, text=True, **kw)

    def test_from_directory_text_json_and_exit_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = staged(Path(tmp))
            text = self.run_tool("--from", str(directory))
            self.assertEqual(text.returncode, 0, text.stderr)
            self.assertIn("Session renders with: Mesa Intel(R) Graphics (ARL)  [hardware, via wayland] on Arrow Lake-S", text.stdout)
            self.assertIn("Hybrid graphics", text.stdout)
            self.assertEqual(json.loads(self.run_tool("--json", "--from", str(directory)).stdout)["verdict"], "accelerated")
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(self.run_tool("--from", empty).returncode, 3)
        self.assertEqual(self.run_tool("--bogus").returncode, 3)

    def test_software_fallback_exits_2(self):
        wayland = (FIXTURES / "msi-eglinfo-wayland.txt").read_text().replace("Mesa Intel(R) Graphics (ARL)", "llvmpipe (LLVM 19.1.7, 256 bits)")
        with tempfile.TemporaryDirectory() as tmp:
            directory = staged(Path(tmp), eglinfo_wayland=wayland)
            self.assertEqual(self.run_tool("--from", str(directory)).returncode, 2)


if __name__ == "__main__":
    unittest.main()
