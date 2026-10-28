/*
 * QEMU test table for hwtrace dev10: an ACPI system resource that claims
 * I/O port 0x70 alone, as the MSI Raider 18 HX does, so atrtc's 0x70-0x71
 * allocation fails the same way.  Compiled with iasl (FreeBSD base);
 * load with qemu-stick-test.py --qemu-arg=-acpitable
 * --qemu-arg=file=tools/boottrace/qemu/rtc-0x70-conflict.aml.
 */
DefinitionBlock ("", "SSDT", 2, "DMNRCH", "RTCCONF", 1)
{
    Scope (\_SB)
    {
        Device (RTCC)
        {
            Name (_HID, EisaId ("PNP0C02"))
            Name (_UID, 0x70)
            Name (_CRS, ResourceTemplate ()
            {
                IO (Decode16, 0x0070, 0x0070, 0x01, 0x01)
            })
        }
    }
}
