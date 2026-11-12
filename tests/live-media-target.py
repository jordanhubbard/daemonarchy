#!/usr/bin/env python3
"""Final admission must reject live media even after a RAM root releases it."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
GUID='fedcba98-7654-3210-fedc-ba9876543210'
OTHER='01234567-89ab-cdef-0123-456789abcdef'
COMMON=r'''
set -euo pipefail
source "$ROOT/overlay/usr/local/libexec/daemonarchy-installer/disk-layout"
glabel() {
  printf '%s\n' "$MEDIA"
  for ((i=0;i<EXTRA;i++)); do printf 'iso9660/OTHER%s OK da9p1\n' "$i"; done
}
kenv() { [[ -n $BOOT_UUID ]] && printf '%s\n' "$BOOT_UUID"; }
gpart() {
  [[ $1 == list ]] || { echo WRITE_ATTEMPT >&2; return 90; }
  [[ $GPT == yes ]] || return 1
  local uuid=$OTHER mode=r0w0e0
  case " $TRACE_DISKS " in *" $2 "*) uuid=$GUID ;; esac
  [[ $2 != "$BUSY" ]] || mode=r1w0e0
  printf 'Geom name: %s\nMode: %s\nrawuuid: %s\n' "$2" "$mode" "$uuid"
}
geom() {
  local mode=r0w0e0
  [[ $3 != "$BUSY" ]] || mode=r1w0e0
  printf 'descr: fixture disk\nMode: %s\n' "$mode"
}
diskinfo() { printf '%s 512 25769803776 0\n' "$1"; }
sysctl() {
  if [[ $* == '-n kern.disks' ]]; then echo 'da0 da1 da2'
  elif [[ $* == '-n machdep.bootmethod' ]]; then echo UEFI
  else return 1; fi
}
'''
BODY=r'''
disk=$CANDIDATE
install_mode=whole_disk disk_snapshot=''
MIN_DISK_BYTES=21474836480
idle=0; disk_is_idle "$disk" 2>/dev/null || idle=$?
admitted=0; validate_install_layout 2>/dev/null || admitted=$?
printf 'STATUS %s %s\n' "$idle" "$admitted"
disk_choices
'''


def observation(**changes):
    config=(ROOT/'overlay/usr/local/libexec/daemonarchy-installer/configurator').read_text()
    start=config.index('disk_choices() {')
    choices=config[start:config.index('\n}',start)+2]
    values=dict(ROOT=str(ROOT),GUID=GUID,OTHER=OTHER,MEDIA='',EXTRA='0',
                BOOT_UUID='',TRACE_DISKS='',BUSY='',GPT='yes',CANDIDATE='da0')
    values.update(changes)
    result=subprocess.run(['bash','-c',COMMON+'\n'+choices+'\n'+BODY],
        env=dict(os.environ,**values),text=True,capture_output=True,check=True)
    if 'WRITE_ATTEMPT' in result.stdout+result.stderr:
        raise AssertionError('read-only admission invoked a mutation')
    lines=result.stdout.splitlines()
    assert lines[0].startswith('STATUS ')
    _,idle,admitted=lines[0].split()
    return int(idle),int(admitted),[line.split('\t')[0] for line in lines[1:]]


class LiveMediaTargets(unittest.TestCase):
    def test_idle_iso_boot_medium_refused_by_ui_and_final_admission(self):
        idle,admitted,choices=observation(MEDIA='iso9660/LIVE OK da0p1')
        self.assertNotEqual(idle,0);self.assertNotEqual(admitted,0)
        self.assertEqual(choices,['da1','da2'])

    def test_multiple_iso_aliases_and_streamed_inventory_do_not_bypass_guard(self):
        for disk in ('da0','da1'):
            idle,admitted,choices=observation(
                MEDIA='iso9660/LIVE OK da0p1\niso9660/SECOND OK da1s1a',
                EXTRA='2000',CANDIDATE=disk)
            self.assertNotEqual(idle,0);self.assertNotEqual(admitted,0)
            self.assertEqual(choices,['da2'])

    def test_kernel_partition_identity_protects_boot_and_cloned_uuid(self):
        for disk in ('da0','da1'):
            idle,admitted,choices=observation(BOOT_UUID=GUID.upper(),
                TRACE_DISKS='da0 da1',CANDIDATE=disk)
            self.assertNotEqual(idle,0);self.assertNotEqual(admitted,0)
            self.assertEqual(choices,['da2'])

    def test_unrelated_idle_target_remains_admissible(self):
        idle,admitted,choices=observation(MEDIA='iso9660/LIVE OK da0',
            BOOT_UUID=GUID,TRACE_DISKS='da0',CANDIDATE='da2')
        self.assertEqual((idle,admitted),(0,0))
        self.assertEqual(choices,['da1','da2'])

    def test_missing_or_malformed_diagnostic_identity_does_not_block_ordinary_targets(self):
        for uuid in ('','not-a-uuid','00000000-0000-0000-0000-000000000000'):
            self.assertEqual(observation(BOOT_UUID=uuid,CANDIDATE='da2')[:2],(0,0))
        self.assertEqual(observation(GPT='no',CANDIDATE='da2')[:2],(0,0))

    def test_busy_disk_refusal_is_retained_without_diagnostic_identity(self):
        for gpt in ('yes','no'):
            idle,admitted,_=observation(BUSY='da2',GPT=gpt,CANDIDATE='da2')
            self.assertNotEqual(idle,0);self.assertNotEqual(admitted,0)


if __name__=='__main__':unittest.main()
