---
name: Hardware report
about: Report the fix on another X571GD, BIOS, or kernel
title: "[report] X571GD BIOS ... / kernel ..."
---

**Laptop / BIOS version:**

**Touchpad ACPI ID / USB HID:**

**Kernel version:**

**Active DSDT size:** output of `stat -c '%s' /sys/firmware/acpi/tables/DSDT`

**Did the override load?** output of `sudo dmesg | grep -iE 'Table Upgrade|ACPI table found in initrd'`

**Symptom with the charger connected:**

**Short libinput excerpt:**

**Anything else:**

Do not paste a full `acpidump`, the root filesystem UUID, hostname, serial
numbers, or a vendor DSDT/AML. A short `TPD0` excerpt and the relevant log
lines are enough.
