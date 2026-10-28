# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Daemonarchy contributors.
<#
.SYNOPSIS
  Read the Daemonarchy reset-surviving boot trace from UEFI NVRAM.

.DESCRIPTION
  A Daemonarchy kernel booted with debug.boottrace=1 stores the startup step
  it was about to run in the UEFI variable DaemonarchyBootTrace
  {9262df38-e448-4c99-bdd0-e70eada0faa1}, with the newest breadcrumbs in the
  ring DBTStep00..DBTStep63 (older kernels: one DBTStep) and the stick
  loader's self-report in DBTLoader.  When the machine hangs or resets
  into Windows, run this script from an elevated PowerShell to turn that
  variable into a readable text file (plus the raw bytes).

  Requires Administrator (SeSystemEnvironmentPrivilege) and UEFI boot.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File read-boottrace.ps1

.EXAMPLE
  .\read-boottrace.ps1 -OutDir C:\Temp -Clear
#>
[CmdletBinding()]
param(
    [string]$OutDir = [Environment]::GetFolderPath('Desktop'),
    [switch]$Clear
)

$ErrorActionPreference = 'Stop'
$VarName = 'DaemonarchyBootTrace'
$VarGuid = '{9262df38-e448-4c99-bdd0-e70eada0faa1}'

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class DaemonarchyFirmware {
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    struct LUID { public uint Low; public int High; }
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    struct TOKEN_PRIVILEGES { public uint Count; public LUID Luid; public uint Attributes; }

    [DllImport("advapi32.dll", SetLastError = true)]
    static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern bool LookupPrivilegeValue(string system, string name, out LUID luid);
    [DllImport("advapi32.dll", SetLastError = true)]
    static extern bool AdjustTokenPrivileges(IntPtr token, bool disableAll,
        ref TOKEN_PRIVILEGES state, uint length, IntPtr previous, IntPtr returnLength);
    [DllImport("kernel32.dll")]
    static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern uint GetFirmwareEnvironmentVariableExW(string name, string guid,
        byte[] buffer, uint size, out uint attributes);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern bool SetFirmwareEnvironmentVariableExW(string name, string guid,
        IntPtr value, uint size, uint attributes);

    public static void EnablePrivilege() {
        IntPtr token;
        if (!OpenProcessToken(GetCurrentProcess(), 0x0028, out token))
            throw new System.ComponentModel.Win32Exception();
        try {
            TOKEN_PRIVILEGES tp = new TOKEN_PRIVILEGES();
            tp.Count = 1;
            tp.Attributes = 2; // SE_PRIVILEGE_ENABLED
            if (!LookupPrivilegeValue(null, "SeSystemEnvironmentPrivilege", out tp.Luid))
                throw new System.ComponentModel.Win32Exception();
            if (!AdjustTokenPrivileges(token, false, ref tp, 0, IntPtr.Zero, IntPtr.Zero))
                throw new System.ComponentModel.Win32Exception();
            if (Marshal.GetLastWin32Error() != 0)
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error(),
                    "SeSystemEnvironmentPrivilege is not held; run PowerShell as Administrator");
        } finally { CloseHandle(token); }
    }

    public static byte[] Read(string name, string guid, out int error) {
        byte[] buffer = new byte[65536];
        uint attributes;
        uint got = GetFirmwareEnvironmentVariableExW(name, guid, buffer, (uint)buffer.Length, out attributes);
        error = got == 0 ? Marshal.GetLastWin32Error() : 0;
        if (got == 0) return null;
        byte[] data = new byte[got];
        Array.Copy(buffer, data, got);
        return data;
    }

    public static int Delete(string name, string guid) {
        return SetFirmwareEnvironmentVariableExW(name, guid, IntPtr.Zero, 0, 7) ? 0 : Marshal.GetLastWin32Error();
    }
}
'@

function Get-CString([byte[]]$Bytes, [int]$Offset, [int]$Length) {
    $end = [Array]::IndexOf($Bytes, [byte]0, $Offset, $Length)
    if ($end -lt 0) { $end = $Offset + $Length }
    return [Text.Encoding]::UTF8.GetString($Bytes, $Offset, $end - $Offset)
}

function Format-StepLine([byte[]]$s) {
    $kinds = @{ 1 = 'sysinit'; 2 = 'probe'; 3 = 'attach'; 4 = 'hook'; 5 = 'event'; 6 = 'panic'; 7 = 'complete' }
    $sk = $kinds[[int][BitConverter]::ToUInt16($s, 20)]; if (-not $sk) { $sk = '?' }
    $sms = [BitConverter]::ToUInt32($s, 16)
    $sl = '#{0} {1}.{2:D3}s cpu{3} {4}: {5}' -f [BitConverter]::ToUInt32($s, 4), [math]::Floor($sms / 1000), ($sms % 1000), [BitConverter]::ToUInt16($s, 22), $sk, (Get-CString $s 24 40)
    if ($sk -eq 'sysinit') { $sl += ' [sub 0x{0:x} order 0x{1:x}]' -f [BitConverter]::ToUInt32($s, 8), [BitConverter]::ToUInt32($s, 12) }
    return $sl
}

# Breadcrumb slots sorted by sequence number, oldest first.
function Sort-Ring($slots) {
    return ,@($slots | Where-Object { $_ -and $_.Length -ge 64 -and [BitConverter]::ToUInt32($_, 0) -gt 0 } |
        Sort-Object { [BitConverter]::ToUInt32($_, 0) })
}

function Format-BootTrace([byte[]]$d, [byte[]]$step, $ring = @()) {
    $magic = [Text.Encoding]::ASCII.GetString($d, 0, 8)
    if ($d.Length -lt 128 -or $magic -ne 'DBTRACE1' -or [BitConverter]::ToUInt16($d, 8) -ne 1) {
        throw "The variable does not hold a version 1 Daemonarchy boot trace."
    }
    $hdrSize = [BitConverter]::ToUInt16($d, 10)
    $crumbSize = [BitConverter]::ToUInt16($d, 12)
    $crumbCount = [BitConverter]::ToUInt16($d, 14)
    $u = { param($o) [BitConverter]::ToUInt32($d, $o) }
    $seq = & $u 20; $status = & $u 24; $flags = & $u 28; $steps = & $u 32
    $resume = & $u 36; $msgLen = & $u 40; $uptime = & $u 44
    $nvLeft = & $u 48; $budget = & $u 52; $nvUsed = & $u 56; $stepWrites = & $u 60
    $kernel = Get-CString $d 64 64
    if ($hdrSize + $crumbCount * $crumbSize + $msgLen -gt $d.Length) {
        throw "The boot trace record is truncated or inconsistent."
    }
    $statusText = @{ 1 = 'INCOMPLETE: the kernel never reached init (hang or reset)';
                     2 = 'complete: the kernel reached init';
                     3 = 'PANIC: the kernel panicked' }[[int]$status]
    if (-not $statusText) { $statusText = 'unknown' }
    $kinds = @{ 1 = 'sysinit'; 2 = 'probe'; 3 = 'attach'; 4 = 'hook'; 5 = 'event'; 6 = 'panic'; 7 = 'complete' }
    $flagNames = @{ 1 = 'loader-seen'; 2 = 'budget-exhausted'; 4 = 'write-error'; 8 = 'fine-window'; 16 = 'test-armed'; 32 = 'saved-to-usb'; 64 = 'thinned'; 128 = 'strided'; 256 = 'runtime-reclaim' }
    $fl = ($flagNames.Keys | Sort-Object | Where-Object { $flags -band $_ } | ForEach-Object { $flagNames[$_] }) -join ','
    if (-not $fl) { $fl = 'none' }

    $crumbs = for ($i = 0; $i -lt $crumbCount; $i++) {
        $o = $hdrSize + $i * $crumbSize
        $kind = $kinds[[int][BitConverter]::ToUInt16($d, $o + 8)]
        if (-not $kind) { $kind = '?' }
        $ms = [BitConverter]::ToUInt32($d, $o + 4)
        $line = '#{0} {1}.{2:D3}s cpu{3} {4}: {5}' -f [BitConverter]::ToUInt32($d, $o), [math]::Floor($ms / 1000), ($ms % 1000), [BitConverter]::ToUInt16($d, $o + 10), $kind, (Get-CString $d ($o + 20) 76)
        if ($kind -eq 'sysinit') {
            $line += ' [sub 0x{0:x} order 0x{1:x}]' -f [BitConverter]::ToUInt32($d, $o + 12), [BitConverter]::ToUInt32($d, $o + 16)
        }
        $line
    }
    $msgOff = $hdrSize + $crumbCount * $crumbSize
    $messages = [Text.Encoding]::UTF8.GetString($d, $msgOff, $msgLen).TrimEnd("`n", "`0")

    $out = New-Object System.Collections.Generic.List[string]
    $out.Add("Daemonarchy boot trace (EFI variable $VarName, write #$seq)")
    $out.Add("Status: $statusText")
    $newest = 0
    if ($crumbCount -gt 0) { $newest = [BitConverter]::ToUInt32($d, $hdrSize + ($crumbCount - 1) * $crumbSize) }
    if ($ring.Count -gt 0) { $step = $ring[-1] }
    if ($step -and $step.Length -ge 64 -and [BitConverter]::ToUInt32($step, 4) -gt $newest -and $status -eq 1) {
        $sl = Format-StepLine $step
        $out.Add("Last step: $sl")
        $out.Add(('      (breadcrumb #{0}; the full record below is from step #{1})' -f [BitConverter]::ToUInt32($step, 0), $steps))
    } elseif ($crumbs) { $out.Add("Last step: " + @($crumbs)[-1]) }
    if ($flags -band 2) { $out.Add("NOTE: the NVRAM write budget ran out at step #$steps, before the failure. Rerun with debug.boottrace.from set just before that step.") }
    $out.Add("Kernel: $kernel")
    $out.Add(('Steps seen: {0}, last full write at {1:N3}s, NVRAM free at start {2} KiB, {3} KiB written, {4} breadcrumbs (budget ~{5}), flags {6}' -f $steps, ($uptime / 1000.0), $nvLeft, $nvUsed, $stepWrites, $budget, $fl))
    if ($resume -eq [uint32]::MaxValue) { $out.Add('Persisted: coarse before debug.boottrace.from_sub, every step after it') }
    else { $out.Add("Persisted: every step from #$resume") }
    $out.Add("Recent steps (oldest first):")
    foreach ($c in $crumbs) { $out.Add("  $c") }
    if ($ring.Count -gt 0) {
        $out.Add("NVRAM breadcrumb ring, $($ring.Count) newest (oldest first):")
        foreach ($r in $ring) { $out.Add(('  b{0} ' -f [BitConverter]::ToUInt32($r, 0)) + (Format-StepLine $r)) }
    }
    $out.Add("Last kernel messages:")
    foreach ($l in $messages -split "`n") { $out.Add("  $l") }
    return ($out -join "`r`n") + "`r`n"
}

[DaemonarchyFirmware]::EnablePrivilege()
$err = 0
$data = [DaemonarchyFirmware]::Read($VarName, $VarGuid, [ref]$err)
if ($null -eq $data) {
    if ($err -eq 203) {
        Write-Host "No Daemonarchy boot trace is stored in NVRAM (ERROR_ENVVAR_NOT_FOUND)."
        exit 2
    }
    if ($err -eq 1) {
        throw "Firmware variables are not available: Windows was not booted in UEFI mode."
    }
    throw (New-Object System.ComponentModel.Win32Exception($err))
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stepErr = 0
$StepNames = @('DBTStep') + (0..63 | ForEach-Object { 'DBTStep{0:D2}' -f $_ })
$slots = foreach ($n in $StepNames) { ,([DaemonarchyFirmware]::Read($n, $VarGuid, [ref]$stepErr)) }
$ring = Sort-Ring $slots
$text = Format-BootTrace $data $null $ring
$ldr = [DaemonarchyFirmware]::Read('DBTLoader', $VarGuid, [ref]$stepErr)
if ($ldr -and $ldr.Length -ge 128 -and [Text.Encoding]::ASCII.GetString($ldr, 0, 8) -eq 'DBTLDR01') {
    $lu = { param($o) [BitConverter]::ToUInt32($ldr, $o) }
    $text += ('Loader self-report (DBTLoader): cycle {0} (epoch {1}) step {2} flags 0x{3:x}; wrote next={4} traces={5} pending={6:D4} (method {7}, read-back {8}); stick had next={9} traces={10}; {11}' -f (& $lu 12), (& $lu 8), (& $lu 16), (& $lu 20), (& $lu 36), (& $lu 40), (& $lu 44), (& $lu 24), (& $lu 32), (& $lu 52), (& $lu 56), (Get-CString $ldr 64 64)) + "`r`n"
}
$txt = Join-Path $OutDir "DaemonarchyBootTrace-$stamp.txt"
$bin = Join-Path $OutDir "DaemonarchyBootTrace-$stamp.bin"
[IO.File]::WriteAllText($txt, $text, (New-Object Text.UTF8Encoding($false)))
[IO.File]::WriteAllBytes($bin, $data)
Write-Host $text
Write-Host "Saved: $txt"
Write-Host "Raw:   $bin"

if ($Clear) {
    foreach ($n in $StepNames) { [void][DaemonarchyFirmware]::Delete($n, $VarGuid) }
    $rc = [DaemonarchyFirmware]::Delete($VarName, $VarGuid)
    if ($rc -ne 0) { throw (New-Object System.ComponentModel.Win32Exception($rc)) }
    Write-Host "The boot trace variable was cleared."
}
