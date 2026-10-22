# Verification

This page records what was checked on the verified machine. It intentionally
omits the full kernel log, the root filesystem UUID, the hostname, and other
machine-specific identifiers.

## Verified configuration

| Item | Value |
|---|---|
| Laptop | ASUS VivoBook X571GD_F571GD |
| BIOS | X571GD.313 (2022-05-03) |
| Touchpad | ELAN1200:00 04F3:3104 |
| ACPI ID | `ELAN1200` |
| ACPI path | `\_SB_.PCI0.I2C0.TPD0` |
| I2C adapter | `i2c-5` DesignWare, PCI `00:15.0` |
| OS | Void Linux |
| Kernel | `6.18.58_1` |
| libinput | 1.31.3 |
| Bootloader | GRUB 2.12 |
| Active DSDT | 263792 bytes |

## Checks

| Check | Result |
|---|---|
| Patch applied to the decompiled DSDT | Pass |
| Patched AML header length and checksum | Pass |
| Override cpio contains `kernel/firmware/acpi/DSDT.aml` | Pass |
| Boot entry loads the override before the initramfs | Pass |
| Active DSDT is 263792 bytes | Pass |
| Touchpad stable with the charger connected | Pass |

## Observed commands

```console
$ uname -r
6.18.58_1

$ stat -c '%s' /sys/firmware/acpi/tables/DSDT
263792

$ ./scripts/verify.sh
kernel: 6.18.58_1
active DSDT: 263792 bytes (expected 263792)

PASS: the active DSDT has the expected patched size.
```

The active DSDT size is the decisive check: the original vendor table is
264082 bytes and the patched table is 263792 bytes, so a size of 263792 means
the kernel accepted and installed the override.

## Expected kernel log

The exact formatting and compiler version depend on the kernel and the `iasl`
build. A successful override produces lines similar to:

```text
ACPI: Table Upgrade: install [DSDT-_ASUS_-Notebook]
ACPI: DSDT 00000000, 040670 (v02 _ASUS_ Notebook 0107200A INTL 20260408)
```

The `0107200A` OEM revision is the important part. The original table uses
`01072009`.

To check your own boot:

```bash
sudo dmesg | grep -iE 'ACPI table found in initrd|Table Upgrade'
```

Some distributions restrict `dmesg` to root. If the command prints nothing,
run it with `sudo` or check the journal for the previous boot.

## Touchpad test

The reporter used the machine normally with the charger connected and
confirmed that the pointer no longer lagged or jumped. To repeat the test:

```bash
sudo libinput debug-events --device /dev/input/event8
```

Adjust the event number to match the touchpad. Leave the charger connected and
watch for:

```text
Touch jump detected and discarded.
```

The absence of that message, together with normal pointer movement, is the
expected result.

## What was not verified

- The kernel quirk patch in `patches/` has not been built or booted on this
  machine. It is a proposed upstream fix, not the verified workaround.
- The procedure has not been tested on other X571GD BIOS versions or on other
  laptop models.
- Secure Boot and kernel lockdown were not enabled during verification.
