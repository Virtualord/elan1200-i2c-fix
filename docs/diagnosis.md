# Diagnosis

## Symptoms

The ASUS VivoBook X571GD touchpad works normally on battery but becomes
sluggish and occasionally jumps when the AC charger is connected. The failure
is reproducible across desktop sessions and does not depend on pointer
acceleration settings.

`libinput` reports the jump explicitly:

```text
Touch jump detected and discarded.
See https://wayland.freedesktop.org/libinput/doc/latest/touchpad-jumping-cursors.html for details
```

The touchpad identifies itself as:

```text
ELAN1200:00 04F3:3104
```

The ACPI device is `ELAN1200` at `\_SB_.PCI0.I2C0.TPD0`. It is connected to the
DesignWare I2C controller at PCI `00:15.0`, which enumerates as `i2c-5` on the
verified machine.

## What the DSDT says

The X571GD DSDT contains four `Device (TPD0)` copies. The first one is the
active device. Inside its `_INI` method, the ELAN1200 branch selects an I2C
speed from the `TPDS` variable:

```asl
If ((TPDT == 0x05))
{
    _HID = "ELAN1200"
    HID2 = TPDH
    BADR = TPDB
    If ((TPDS == Zero))
    {
        SPED = 0x000186A0
    }
    If ((TPDS == One))
    {
        SPED = 0x00061A80
    }
    If ((TPDS == 0x02))
    {
        SPED = 0x000F4240
    }
    Return (Zero)
}
```

The values map to:

| `TPDS` | `SPED` | Speed |
|---|---|---:|
| `Zero` | `0x000186A0` | 100 kHz |
| `One` | `0x00061A80` | 400 kHz |
| `0x02` | `0x000F4240` | 1 MHz |

The device also has a `Name (SBFB, Buffer (0x19))` descriptor. At offset
`0x0C`, the default speed is encoded as:

```text
0x80, 0x1A, 0x06, 0x00
```

which is `0x00061A80`, or 400 kHz. The verified patch changes those four bytes
to:

```text
0xA0, 0x86, 0x01, 0x00
```

which is `0x000186A0`, or 100 kHz.

On the verified machine, the firmware selects the 400 kHz path. The patch
removes the three conditional branches and writes the 100 kHz value
unconditionally for the active device.

## Why the charger matters

The failure only appears on AC power. That points to a change in electrical
conditions on the I2C bus, not to a userspace input configuration problem.
Charger noise, power-rail behavior, or a firmware power state can reduce the
signal margin at 400 kHz. The ELAN firmware then applies excessive smoothing
or reports a jump.

The exact mechanism is not documented by ELAN. The upstream kernel commit for
the ELAN06FA states that the root cause is not fully known, but that the
100 kHz workaround is effective. The ELAN0678 and ELAN1300 commits describe
the same symptoms and use the same workaround.

The verified fix does not require a grounded charger, a different power
supply, or a hardware modification. It gives the touchpad more timing margin
by lowering the bus speed.

## Why userspace settings do not help

Pointer acceleration, tap-to-click, and libinput quirks operate after the
touchpad firmware has produced events. The jumps originate in the firmware's
handling of the I2C traffic. Changing userspace settings can make the pointer
feel different, but it cannot remove the underlying bad reports.

The verified fix changes the bus description before the kernel initializes the
I2C client, so the controller and the device communicate at 100 kHz from the
start.

## Upstream context

The kernel has a list of ACPI device IDs that are forced to 100 kHz:

```c
static const struct acpi_device_id i2c_acpi_force_100khz_device_ids[] = {
    { "DLL0945", 0 },
    { "ELAN0678", 0 },
    { "ELAN06FA", 0 },
    { "ELAN1300", 0 },
    {}
};
```

Relevant commits:

- `ELAN06FA`: `bfd74cd1fbc026f04446e67d6915c7e199c2bffd`
- `ELAN0678`: `9998e388be9930c106eb5904c23ecf2162407527`
- `ELAN1300`: `9e9762e578db7556bea644bb5a8a2435f63544d1`

The ELAN1300 commit is especially relevant: it covers an ASUS VivoBook
X513UA with the same USB HID ID, `04F3:3104`, and the same touch-jump symptom.
The ACPI ID, not the USB HID, is what the kernel quirk matches.

`ELAN1200` is absent from the list. That is why the X571GD still runs its
touchpad bus at 400 kHz on an unpatched kernel.

## The two fixes

### DSDT override

The verified workaround replaces the active device's speed selection with a
single 100 kHz assignment and increments the DSDT OEM revision. The new table
is packed into an uncompressed cpio at:

```text
kernel/firmware/acpi/DSDT.aml
```

The kernel's ACPI table upgrade code scans the initrd before the normal
initramfs, validates the table, and installs it if the OEM ID and OEM table ID
match and the OEM revision is greater than the current table's revision.

This is the approach used on the verified machine.

### Kernel quirk patch

The long-term fix is to add `ELAN1200` to
`i2c_acpi_force_100khz_device_ids`. The patch in `patches/` does that. It is
the same mechanism the kernel already uses for the other ELAN models.

The kernel patch is a proposal and has not been merged. The DSDT override is
the verified fix.

## Why not change the charger or grounding

The charger correlation is a trigger, not something the verified fix depends
on. The evidence points to the bus being marginal at 400 kHz, and the charger
changes the electrical environment enough to expose it. Grounding or replacing
the charger may change the symptom on one machine, but it does not address the
bus timing and is not a reliable fix.

The verified solution is kernel/firmware-level and works while charging without
touching the charger or the hardware.

## References

- [Linux `i2c-core-acpi.c`](https://github.com/torvalds/linux/blob/master/drivers/i2c/i2c-core-acpi.c)
- [Linux `drivers/acpi/tables.c`](https://github.com/torvalds/linux/blob/master/drivers/acpi/tables.c)
- [libinput touchpad jumping](https://wayland.freedesktop.org/libinput/doc/latest/touchpad-jumping-cursors.html)
- [ACPICA](https://www.acpica.org/)
- [Arch Wiki: DSDT](https://wiki.archlinux.org/title/DSDT)
