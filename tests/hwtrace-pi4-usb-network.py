#!/usr/bin/env python3
"""Reject SD loader/root fallback despite successful USB enumeration or GENET."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('usb_control', Path(__file__).resolve().parents[1] / 'tools/hwtrace/pi4-usb-network-simulator.py')
usb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usb)
USB_PATH = '/VenHw(controller)/Pci(0x0,0x0)/USB(0x0,0x0)/HD(1,GPT,id,0x22,0x14000)'
SD_PATH = '/VenHw(controller)/SD(1)/SD(0)/HD(1,GPT,id,0x22,0x14000)'
SERIAL = ('USB XHCI 1.00\nscanning usb for storage devices... 1 Storage Device(s) found\n'
          'Booting: Label: usb 0 Device path: ' + USB_PATH + '\nLoad Device: ' + USB_PATH + '\n'
          'pcib0: <BCM2838-compatible PCI-express controller> on simplebus2\n'
          'xhci0: <XHCI (generic) USB 3.0 controller> irq 92 at device 0.0 on pci1\n'
          'umass0: <QEMU USB HARDDRIVE> on usbus1\nda0: <QEMU HARDDISK>\n')
MOUNTS = '/dev/gpt/HWTROOT / ufs ro 0 0\n'
GEOM = ('<mesh><class><name>DISK</name><geom><provider id="disk">'
        '<name>da0</name></provider></geom></class>'
        '<class><name>PART</name><geom><consumer><provider ref="disk"/></consumer>'
        '<provider id="part"><name>da0p2</name></provider></geom></class>'
        '<class><name>LABEL</name><geom><consumer><provider ref="part"/></consumer>'
        '<provider id="label"><name>gpt/HWTROOT</name></provider></geom></class></mesh>')


class USBOnlyGuards(unittest.TestCase):
    def test_single_usb_attachment_replaces_sd_instead_of_adding_fallback(self):
        command = usb.usb_command(['qemu', '-drive', 'if=sd,format=qcow2,file=/private/disk.qcow2', '-nic', 'none'])
        self.assertEqual(command.count('-drive'), 1)
        self.assertIn('if=none,id=usb-root,format=qcow2,file=/private/disk.qcow2', command)
        self.assertIn('usb-storage,bus=bcm-xhci.0,drive=usb-root', command)
        self.assertFalse(any('if=sd' in value for value in command))
        for fallback in (['-drive', 'if=sd,file=other'], ['-sd', 'other'],
                         ['-hda', 'other'], ['-blockdev', 'driver=file,filename=other'],
                         ['-device', 'sd-card,drive=other']):
            with self.assertRaises(ValueError):
                usb.validate_usb_command(command + fallback)
        with self.assertRaises(ValueError):
            usb.usb_command(['qemu', '-drive', 'if=sd,format=qcow2,file=first', '-drive', 'if=none,file=second'])

    def test_usb_root_and_usb_enumeration_do_not_hide_an_sd_efi_loader(self):
        checks = usb.usb_root_checks(SERIAL.replace(USB_PATH, SD_PATH), MOUNTS, 'kern.disks: da0\n', GEOM)
        self.assertFalse(checks['usb_efi_load_device'])
        self.assertTrue(checks['native_usb_mass_storage'])
        self.assertTrue(checks['usb_root_geom_da0'])

    def test_efi_path_is_unique_usb_and_contains_no_sd_node(self):
        self.assertTrue(all(usb.usb_root_checks(SERIAL, MOUNTS, 'kern.disks: da0\n', GEOM).values()))
        for serial in (SERIAL.replace('Load Device:', 'Load Path:'), SERIAL + 'Load Device: ' + SD_PATH + '\n',
                       SERIAL.replace(USB_PATH, USB_PATH + '/SD(0)')):
            self.assertFalse(usb.usb_root_checks(serial, MOUNTS, 'kern.disks: da0\n', GEOM)['usb_efi_load_device'])

    def test_uboot_usb_controller_storage_and_selected_bootflow_are_required(self):
        for original, key in [('USB XHCI 1.00', 'uboot_usb_storage'),
                              ('1 Storage Device(s) found', 'uboot_usb_storage'),
                              ('Booting: Label: usb 0', 'uboot_usb_bootflow')]:
            self.assertFalse(usb.usb_root_checks(SERIAL.replace(original, 'absent'),
                MOUNTS, 'kern.disks: da0\n', GEOM)[key])

    def test_native_geom_resolves_root_label_to_usb_disk_not_sd(self):
        self.assertEqual(usb.root_disk(GEOM, '/dev/gpt/HWTROOT'), {'da0'})
        self.assertEqual(usb.root_disk(GEOM + '\0', '/dev/gpt/HWTROOT'), {'da0'})
        checks = usb.usb_root_checks(SERIAL, MOUNTS, 'kern.disks: da0 mmcsd0\n', GEOM.replace('<name>da0</name>', '<name>mmcsd0</name>'))
        self.assertFalse(checks['usb_root_geom_da0'])
        self.assertFalse(checks['no_native_sd_disk'])

    def test_missing_cyclic_ambiguous_or_partial_topology_cannot_prove_root(self):
        for text in ('', GEOM[:-10], GEOM.replace('ref="part"', 'ref="absent"'),
                     GEOM.replace('ref="part"', 'ref="label"'),
                     GEOM.replace('id="part"', 'id="disk"'),
                     GEOM.replace('<name>da0p2</name>', '<name>gpt/HWTROOT</name>'), 'x' * ((1 << 20) + 1)):
            self.assertEqual(usb.root_disk(text, '/dev/gpt/HWTROOT'), set())

    def test_root_must_be_one_readonly_ufs_mount_with_native_usb_chain(self):
        for mounts in ('', MOUNTS + MOUNTS, MOUNTS.replace('ufs', 'msdosfs'), MOUNTS.replace(' ro ', ' rw ')):
            self.assertFalse(usb.usb_root_checks(SERIAL, mounts, 'kern.disks: da0\n', GEOM)['usb_ufs_root_readonly'])
        for marker, key in [('pcib0:', 'native_bcm_pcie'), ('xhci0:', 'native_pci_xhci'),
                            ('umass0:', 'native_usb_mass_storage'), ('da0:', 'native_usb_mass_storage')]:
            self.assertFalse(usb.usb_root_checks(SERIAL.replace(marker, 'absent:'), MOUNTS, 'kern.disks: da0\n', GEOM)[key])


if __name__ == '__main__':
    unittest.main()
