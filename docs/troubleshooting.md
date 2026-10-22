# Troubleshooting

## Quick checks

```bash
uname -r
stat -c '%s' /sys/firmware/acpi/tables/DSDT
sudo dmesg | grep -iE 'ACPI table found in initrd|Table Upgrade|ACPI Error'
```

For the verified X571GD:

| Value | Meaning |
|---|---|
| `263792` | Patched DSDT is active |
| `264082` | Original DSDT is still active |
| `Table Upgrade` in `dmesg` | Kernel accepted an override |
| `ACPI Error` around table upgrade | The override was rejected |

## The override did not load

### Check the cpio path

The archive must contain this path:

```text
kernel/firmware/acpi/DSDT.aml
```

Check it with:

```bash
cpio -it < /boot/acpi-fix.cpio
```

If the path is different, rebuild the cpio with
`scripts/build-cpio.sh`.

### Check the initrd order

The override must be listed **before** the normal initramfs:

```grub
initrd /boot/acpi-fix.cpio /boot/initramfs-6.18.58_1.img
```

For systemd-boot, use two `initrd` lines in the same order:

```ini
initrd  /acpi-fix.cpio
initrd  /initramfs-linux.img
```

If the normal initramfs comes first, the kernel may not see the override.

### Check the cpio format

The cpio must be an uncompressed `newc` archive. It must not be gzip, xz, or
zstd compressed. Check the first bytes:

```bash
od -An -tx1 -N6 /boot/acpi-fix.cpio
```

A `newc` archive starts with the ASCII string `070701`, which is
`30 37 30 37 30 31` in hex.

### Check the boot entry

Make sure the bootloader is actually loading the entry you think it is. The
entry title is not proof; check the kernel command line and the initrd list in
the bootloader menu.

```bash
cat /proc/cmdline
```

The override cpio does not appear in `/proc/cmdline`; it appears in the
bootloader's initrd list. If you have multiple entries with similar names,
select the correct one explicitly.

### Check Secure Boot and lockdown

```bash
mokutil --sb-state 2>/dev/null || true
cat /sys/kernel/security/lockdown 2>/dev/null || true
```

If Secure Boot is enabled or lockdown is active, the kernel rejects an
unsigned ACPI override. Disable Secure Boot for testing, or sign the boot
components with your own key.

### Check kernel support

```bash
grep -E '^CONFIG_ACPI_TABLE_UPGRADE=' /boot/config-"$(uname -r)"
```

The value must be `y`. If it is missing or `n`, the kernel cannot install the
override. Use a kernel with the option enabled or use the kernel quirk patch.

## The DSDT size is still 264082

The original table is still active. Check, in order:

1. The cpio contains `kernel/firmware/acpi/DSDT.aml`.
2. The cpio is uncompressed `newc`.
3. The cpio is first in the initrd list.
4. The boot entry is the one being booted.
5. Secure Boot and lockdown are disabled for testing.
6. `CONFIG_ACPI_TABLE_UPGRADE=y`.
7. The patched AML header is valid.

Validate the AML directly:

```bash
python3 scripts/dsdt_info.py work/dsdt-patched.aml
```

The header length must equal the file size, and the checksum must be valid.
If the AML is invalid, recompile it with `iasl -f -sa`.

## The kernel rejects the table

Check the log for the reason:

```bash
sudo dmesg | grep -iE 'ACPI|DSDT|override|Table Upgrade' | tail -50
```

Common causes:

| Message or symptom | Cause | Fix |
|---|---|---|
| No `Table Upgrade` line | cpio not loaded | Fix initrd order/path |
| Checksum error | AML header invalid | Recompile with `iasl -f -sa` |
| Length mismatch | Header length does not match file size | Recompile; do not truncate the AML |
| OEM ID/table mismatch | Wrong DSDT or wrong table | Use the X571GD DSDT |
| Revision not greater | OEM revision was not bumped | Re-run `patch_dsdt.py` |
| Lockdown error | Secure Boot/lockdown | Disable for testing or sign |

## `iasl` reports errors or warnings

The vendor DSDT may produce duplicate-case or external-symbol warnings. The
verified build used:

```bash
iasl -f -sa work/dsdt-patched.dsl
```

`-f` forces AML output even when the compiler reports the known vendor errors.
`-sa` keeps the output in the current directory. Check that the AML exists
before building the cpio:

```bash
ls -l work/dsdt-patched.aml
python3 scripts/dsdt_info.py work/dsdt-patched.aml
```

If `iasl` produces no AML at all, do not continue. Fix the compile error first.

## The patch tool refuses to run

The tool is intentionally strict. It only supports the X571GD layout:

- `Device (TPD0)`
- `_HID` or `Name (_HID, ...)` equal to `ELAN1200`
- `Name (SBFB, Buffer (...))`
- `If ((TPDT == 0x05))`
- `TPDS` speed branches `Zero`, `One`, `0x02`

If any of these are missing, the tool exits with an error instead of guessing.
This is deliberate: patching the wrong `TPD0` copy can make the touchpad worse
or leave the machine without a working touchpad.

The X571GD DSDT contains four `TPD0` copies. The tool prints:

```text
warning: 4 TPD0 blocks contain ELAN1200; patching the first one
```

This is expected. The first copy is the active device. Review the diff to
confirm the patch was applied at the expected location.

## The touchpad is still unstable

First confirm the override is active:

```bash
stat -c '%s' /sys/firmware/acpi/tables/DSDT
```

If the size is 264082, the override did not load. Work through the previous
sections before changing anything else.

If the size is 263792 but the touchpad is still unstable:

1. Test with `libinput debug-events` and check whether the jump messages are
   still present.
2. Confirm the charger test is long enough; the problem may be intermittent.
3. Check whether the touchpad is using the expected input device.
4. Try the normal entry to confirm the symptom returns there.
5. Report the result with the active DSDT size, kernel version, and a short
   `libinput` excerpt. Do not post a full `acpidump`; it can contain
   machine-specific identifiers.

## GRUB does not show the new entry

Check that `custom.cfg` is sourced:

```bash
sudo grep -n 'custom.cfg' /boot/grub/grub.cfg
```

If it is not, add the entry to `/etc/grub.d/40_custom` and regenerate:

```bash
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

On some distributions the command is `grub2-mkconfig`. Use the one provided by
your GRUB package.

Validate the entry syntax:

```bash
sudo grub-script-check /boot/grub/custom.cfg
```

## systemd-boot does not show the new entry

- Entries must be in the `loader/entries` directory on the ESP.
- Paths are relative to the ESP, not to `/boot`.
- The cpio must be on the same ESP.
- Run `bootctl list` and check for syntax errors.
- If the ESP is mounted at `/boot/efi`, the cpio must be at
  `/boot/efi/acpi-fix.cpio` and referenced as `/acpi-fix.cpio`.

## After a kernel update

The boot entry still points to the old kernel and initramfs paths. Update the
entry, or regenerate it from your bootloader configuration. The override cpio
does not depend on the kernel version and does not need to be rebuilt.

If you use a UKI, rebuild the image with the override cpio prepended.

## `dmesg` says permission denied

Many distributions restrict kernel logs to root:

```bash
sudo dmesg | grep -iE 'ACPI table found in initrd|Table Upgrade'
```

If `dmesg` is unavailable, use your distribution's journal for the current or
previous boot.

## Rollback

Boot the normal entry. The override is not written to firmware.

```bash
sudo rm -f /boot/acpi-fix.cpio /boot/grub/custom.cfg
```

Remove the systemd-boot entry or rebuild the UKI if applicable. If you edited
`/etc/grub.d/40_custom`, remove the block and regenerate `grub.cfg`.

## Reporting a problem

Include:

- Laptop model and BIOS version
- Touchpad name and ACPI ID
- Kernel version
- Active DSDT size
- The relevant `dmesg` lines
- The output of `libinput debug-events` around a jump

Do not include a full `acpidump`, the root filesystem UUID, the hostname, or
serial numbers. The relevant `TPD0` block and a short log excerpt are enough.
