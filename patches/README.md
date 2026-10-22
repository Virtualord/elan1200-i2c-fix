# Kernel patch

`0001-i2c-acpi-add-ELAN1200-to-100khz-quirk.patch` adds the `ELAN1200` ACPI
device ID to `i2c_acpi_force_100khz_device_ids` in
`drivers/i2c/i2c-core-acpi.c`.

This is the long-term fix. The DSDT override in this repository is the
verified workaround for the ASUS VivoBook X571GD.

## What it changes

```diff
 	{ "ELAN06FA", 0 },
+	{ "ELAN1200", 0 },
 	{ "ELAN1300", 0 },
```

The kernel already forces the listed ELAN touchpads to 100 kHz. `ELAN1200` is
the ACPI ID used by the X571GD touchpad (`04F3:3104`); it is a different ID
from the models already covered, so it needs its own entry.

## Target tree

The patch was generated against current `torvalds/linux` master. Line numbers
and surrounding context can drift as the file changes; use `git am` or rebase
the patch if it no longer applies cleanly.

Older stable kernels may have a shorter list, so this patch may need a
rebase before applying it there. The DSDT override works independently of
the kernel version.

## Apply and build

```bash
git am 0001-i2c-acpi-add-ELAN1200-to-100khz-quirk.patch
```

Then build and install your kernel as usual. Confirm the quirk is active:

```bash
sudo dmesg | grep -i i2c
```

The touchpad bus should now be described as 100 kHz. You can also check the
active DSDT as a cross-check; if the firmware still says 400 kHz, the kernel
quirk overrides the bus speed at runtime.

## Submit upstream

The kernel style is one logical change per patch. Keep the commit message and
`Signed-off-by` intact:

```bash
git send-email \
  --to=linux-i2c@vger.kernel.org \
  --cc=linux-acpi@vger.kernel.org \
  0001-i2c-acpi-add-ELAN1200-to-100khz-quirk.patch
```

Before submitting, check the current maintainer list in `MAINTAINERS` and
rebase onto the latest i2c tree. The patch may need a `Tested-by` tag from
another X571GD owner; do not add tags you cannot justify.

## Test evidence

The DSDT override was verified on:

- ASUS VivoBook X571GD_F571GD
- BIOS X571GD.313
- Kernel `6.18.58_1`
- Active DSDT 263792 bytes
- No touchpad lag or jumps with the charger connected

The kernel patch itself has not been merged or booted on the verified machine.
It uses the same quirk mechanism as the existing ELAN entries.

## License

The patch is intended for the Linux kernel and is licensed under
`GPL-2.0-only`, matching the kernel source.
