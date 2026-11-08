#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Verify native U-Boot USB EFI boot, FDT USB/UFS root and GENET SSH/SCP.

No SD image is attached. USB enumeration after an SD loader cannot qualify.
Uses the existing private-image, trusted-SSH and offline-diagnostics controls.
"""
import importlib.util
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pi4_usb_network', HERE / 'pi4-network-simulator.py')
network = importlib.util.module_from_spec(spec)
spec.loader.exec_module(network)
sim = network.sim


def usb_command(command):
    """Replace the sole SD attachment; never retain an alternate boot medium."""
    command = list(command)
    positions = [n for n, value in enumerate(command) if value == '-drive']
    if len(positions) != 1:
        raise ValueError('USB-only control requires exactly one backing image')
    position = positions[0]
    drive = command[position + 1]
    prefix = 'if=sd,format=qcow2,file='
    if not drive.startswith(prefix):
        raise ValueError('unexpected source attachment; refuse an ambiguous boot path')
    command[position + 1] = 'if=none,id=usb-root,format=qcow2,file=' + drive[len(prefix):]
    command += ['-global', 'bcm2838-pcie-disconnected.connected-xhci=on',
                '-device', 'usb-storage,bus=bcm-xhci.0,drive=usb-root']
    validate_usb_command(command)
    return command


def validate_usb_command(command):
    drives = [command[n + 1] for n, value in enumerate(command[:-1]) if value == '-drive']
    devices = [command[n + 1] for n, value in enumerate(command[:-1]) if value == '-device']
    if (len(drives) != 1 or not drives[0].startswith('if=none,id=usb-root,format=qcow2,file=') or
            devices != ['usb-storage,bus=bcm-xhci.0,drive=usb-root'] or
            '-hda' in command or '-hdb' in command or '-sd' in command or
            '-cdrom' in command or '-blockdev' in command):
        raise ValueError('USB-only command contains an alternate or unexpected disk attachment')


def root_disk(xml, name):
    """Resolve a mounted GEOM provider through consumers to actual DISK providers."""
    if len(xml) > 1 << 20:
        return set()
    try:
        # kern.geom.confxml uses SBUF_INCLUDENUL; sysctl -b preserves that byte.
        tree = ET.fromstring(xml.removesuffix("\0"))
    except ET.ParseError:
        return set()
    providers, names = {}, {}
    for cls in tree.findall('class'):
        kind = cls.findtext('name')
        for geom in cls.findall('geom'):
            parents = [p.get('ref') for p in geom.findall('consumer/provider')]
            for provider in geom.findall('provider'):
                ident, label = provider.get('id'), provider.findtext('name')
                if not ident or not label or ident in providers:
                    return set()
                providers[ident] = (kind, label, parents)
                names.setdefault(label, []).append(ident)
    starts = names.get(name.removeprefix('/dev/'), [])
    if len(starts) != 1:
        return set()
    visited, disks = set(), set()
    def walk(ident):
        if ident in visited or ident not in providers:
            return False
        visited.add(ident)
        kind, label, parents = providers[ident]
        if kind == 'DISK':
            disks.add(label)
            return True
        return bool(parents) and all(walk(parent) for parent in parents)
    return disks if walk(starts[0]) else set()


def usb_root_checks(serial, mounts, disks, geom):
    paths = re.findall(r'^\s*Load Device:\s*(\S+)\s*$', serial, re.MULTILINE)
    path = paths[0] if len(paths) == 1 else ''
    roots = [line.split() for line in mounts.splitlines() if len(line.split()) >= 4 and line.split()[1] == '/']
    root = roots[0] if len(roots) == 1 else []
    listed = re.findall(r'^kern\.disks:\s*(.*)$', disks, re.MULTILINE)
    disk_names = listed[0].split() if len(listed) == 1 else []
    return {
        'uboot_usb_storage': 'USB XHCI 1.00' in serial and bool(re.search(
            r'scanning usb for storage devices\.\.\.\s+1 Storage Device\(s\) found', serial)),
        'uboot_usb_bootflow': bool(re.search(r'^Booting: Label: usb 0 Device path:.*?/USB\(', serial, re.MULTILINE)),
        'usb_efi_load_device': bool(re.search(r'/(?:USB|UsbClass|UsbWwid)\(', path, re.IGNORECASE)) and
            not re.search(r'/(?:SD|eMMC)\(', path, re.IGNORECASE),
        'native_bcm_pcie': bool(re.search(r'^pcib\d+: <BCM2838-compatible PCI-express controller>', serial, re.MULTILINE)),
        'native_pci_xhci': bool(re.search(r'^xhci\d+: <.*>.* on pci\d+\s*$', serial, re.MULTILINE)),
        'native_usb_mass_storage': bool(re.search(r'^umass0: <.*> on usbus\d+\s*$', serial, re.MULTILINE)) and
            bool(re.search(r'^da0: <', serial, re.MULTILINE)),
        'usb_ufs_root_readonly': bool(root) and root[2] == 'ufs' and 'ro' in root[3].split(','),
        'usb_root_geom_da0': bool(root) and root_disk(geom, root[0]) == {'da0'},
        'no_native_sd_disk': 'da0' in disk_names and not any(name.startswith('mmcsd') for name in disk_names),
    }


class USBNetworkControl(network.NetworkControl):
    exact_disk_size = True
    profile = 'uboot-fdt-usb-genet'
    success_description = 'USB-only EFI boot, native USB/UFS root, GENET transfers and clean reset'
    boot_checks = {key: value for key, value in sim.CHECKS.items() if key not in ('native_sd', 'sd_root')}
    boot_checks['ufs_root'] = 'Trying to mount root from ufs:/dev/gpt/HWTROOT [ro]'

    def prepare(self, control, queue, output):
        super().prepare(control, queue, output)
        self.report.update(usb_harness_sha256=sim.digest(Path(__file__).resolve()),
                           storage='USB only; no SD backing image; exact image capacity')
        self.save()

    def configure_command(self, command):
        result = usb_command(super().configure_command(command))
        validate_usb_command(result)
        return result

    def collect_extra(self):
        # These are kernel observations over the already authenticated native NIC.
        self.remote('mount -t msdosfs -o sync /dev/gpt/DATRACE /mnt; '
                    '/sbin/mount -p > /mnt/DUMPS/0001/usb-mounts.txt; '
                    '/sbin/sysctl kern.disks > /mnt/DUMPS/0001/usb-disks.txt; '
                    '/sbin/sysctl -b kern.geom.confxml > /mnt/DUMPS/0001/usb-geom.xml; '
                    'sync; umount /mnt')

    def assess(self, dumps):
        checks = super().assess(dumps)
        serial = (self.output / 'serial-clean.txt').read_text(errors='replace').replace('\r', '')
        checks.update(usb_root_checks(serial,
            (dumps / 'usb-mounts.txt').read_text(),
            (dumps / 'usb-disks.txt').read_text(),
            (dumps / 'usb-geom.xml').read_text()))
        self.report['offline_checks'] = checks
        self.report['ok'] = all(checks.values()) and self.report.get('transport_complete') is True
        self.save()
        return checks


if __name__ == '__main__':
    network.main(USBNetworkControl, __doc__)
