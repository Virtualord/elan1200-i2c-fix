# ASUS VivoBook X571GD ELAN1200 I2C 100 kHz Fix

Fix the ELAN1200 touchpad lag and pointer jumps that appear when the AC
charger is connected on the ASUS VivoBook X571GD.

The verified workaround is a DSDT override that forces the touchpad I2C bus
to 100 kHz instead of 400 kHz. The repository also contains an upstream
kernel quirk patch that adds the ELAN1200 to the kernel's existing 100 kHz
device list.

> **Status: verified.** On 2026-10-22 the patched DSDT was loaded through an
> initrd ACPI override on kernel `6.18.58_1`. The active DSDT is 263792 bytes
> and the touchpad no longer lags or jumps with the charger connected.

## The problem

On AC power, the touchpad becomes sluggish and occasionally jumps to a
different position. `libinput` reports:

```text
Touch jump detected and discarded.
See https://wayland.freedesktop.org/libinput/doc/latest/touchpad-jumping-cursors.html for details
```

The same machine is fine on battery. Changing pointer acceleration, disabling
tap-to-click, or re-seating the charger does not fix it.

The X571GD DSDT describes the ELAN1200 I2C bus at `0x00061A80` (400 kHz).
The Linux kernel already forces several other ELAN touchpads to 100 kHz for
the same class of failure, but `ELAN1200` is not in that list.

## The fix

Two equivalent approaches are documented:

| Approach | Status | Scope |
|---|---|---|
| DSDT override with an initrd cpio | Verified on the X571GD | Works on any kernel with ACPI table upgrade support |
| Kernel quirk patch | Proposed upstream fix | Needs a kernel build or a future kernel release |

The DSDT override changes the active `Device (TPD0)` block so the bus is
always described as 100 kHz:

```asl
SPED = 0x000186A0
```

It also bumps the DSDT OEM revision from `0x01072009` to `0x0107200A` so the
kernel accepts the table as an upgrade. The override is loaded before the
normal initramfs and never writes to the firmware.

### Before and after

| Property | Original | Patched |
|---|---:|---:|
| DSDT size | 264082 bytes | 263792 bytes |
| OEM revision | `0x01072009` | `0x0107200A` |
| Checksum | `0x2B` | `0x11` |
| ELAN1200 I2C speed | 400 kHz | 100 kHz |

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
| Active DSDT | 263792 bytes |
| Charger test | Passed, no lag or jumps |

See [`docs/verification.md`](docs/verification.md) for the verification
commands and observations.

## Quick start for X571GD owners

This procedure is for the X571GD with the DSDT layout described above. It is
not a generic ACPI override tutorial. Keep your normal boot entry available;
if the override is malformed, the machine may not boot until you select it.

### 1. Requirements

- Linux with `CONFIG_ACPI_TABLE_UPGRADE=y`
- ACPICA tools: `acpidump`, `acpixtract`, `iasl`
- `cpio`, `python3`
- GRUB, systemd-boot, or another bootloader that can prepend an initrd
- Secure Boot disabled, or a signed kernel/initramfs chain that includes the override

Package names for common distributions are listed in
[`docs/other-distros.md`](docs/other-distros.md).

### 2. Dump and decompile the DSDT

```bash
git clone https://github.com/Virtualord/elan1200-i2c-fix.git
cd elan1200-i2c-fix

mkdir -p work
cd work
sudo acpidump > acpidump.txt
acpixtract -a acpidump.txt
iasl -d dsdt.dat
cd ..
```

This produces `dsdt.dsl`. Confirm that it contains the expected devices:

```bash
grep -n 'Device (TPD0)' dsdt.dsl
grep -n 'ELAN1200' dsdt.dsl
grep -n 'Name (SBFB' dsdt.dsl
```

The X571GD DSDT contains four `TPD0` copies. The first one is the active
device and the one this tool patches.

### 3. Apply the ASL patch

From the repository root:

```bash
python3 scripts/patch_dsdt.py work/dsdt.dsl -o work/dsdt-patched.dsl --diff
```

The tool is deliberately strict. It refuses to patch a file without the
X571GD `TPD0` / `ELAN1200` / `SBFB` / `TPDS` layout. Review the diff before
continuing.

### 4. Compile the patched DSDT

```bash
iasl -f -sa work/dsdt-patched.dsl
```

`iasl` may print duplicate-case or external-symbol warnings from the original
vendor DSDT. The `-f` flag still emits the AML. Verify the result:

```bash
python3 scripts/dsdt_info.py work/dsdt-patched.aml
```

The header length must match the file size and the checksum must be valid.

### 5. Build the override cpio

```bash
./scripts/build-cpio.sh -o work/acpi-fix.cpio work/dsdt-patched.aml
```

The cpio must contain this path:

```text
kernel/firmware/acpi/DSDT.aml
```

Do not gzip the cpio. The kernel's ACPI initrd scanner expects the uncompressed
newc archive.

### 6. Install the override and boot entry

```bash
sudo install -m 0644 work/acpi-fix.cpio /boot/acpi-fix.cpio
sudo install -m 0644 examples/custom.cfg.example /boot/grub/custom.cfg
```

Edit `/boot/grub/custom.cfg` and replace the placeholders with the `linux` and
`initrd` lines from your normal GRUB entry. Put the override cpio **first** in
the `initrd` line:

```grub
menuentry "Linux (ELAN1200 100 kHz DSDT fix)" {
    linux /boot/vmlinuz-6.18.58_1 root=UUID=<YOUR-ROOT-UUID> ro loglevel=4
    initrd /boot/acpi-fix.cpio /boot/initramfs-6.18.58_1.img
}
```

Most distributions source `/boot/grub/custom.cfg` from `41_custom`. Check with:

```bash
sudo grep -n 'custom.cfg' /boot/grub/grub.cfg
```

If your GRUB configuration does not include it, add the entry to
`/etc/grub.d/40_custom` and regenerate `grub.cfg`.

### 7. Reboot and verify

Select the new entry, then run:

```bash
./scripts/verify.sh
sudo dmesg | grep -iE 'ACPI table found in initrd|Table Upgrade'
```

Expected observations:

```text
kernel: 6.18.58_1
active DSDT: 263792 bytes (expected 263792)
ACPI: Table Upgrade: install [DSDT-_ASUS_-Notebook]
ACPI: DSDT 00000000, 040670 (v02 _ASUS_ Notebook 0107200A INTL 20260408)
```

The exact log formatting and compiler version depend on the kernel and the
`iasl` build. The important parts are the `Table Upgrade` line and the
`0107200A` OEM revision.

Finally, use the touchpad for several minutes with the charger connected and
watch for the `Touch jump detected and discarded` message.

## Why 100 kHz?

The upstream kernel already contains this quirk for other ELAN touchpads:

- `ELAN06FA` — ASUS ExpertBook B9400CEA
- `ELAN0678` — ASUS Zenbook UX3402VA
- `ELAN1300` — ASUS VivoBook X513UA

The upstream commit messages describe the same symptoms: sluggish movement and
touch jumps that only appear when the laptop is plugged into AC power. The
exact root cause is not fully understood, but the 100 kHz workaround is
effective. The ELAN1200 on the X571GD is a different ACPI ID from the models
already covered, so it needs its own entry.

See [`docs/diagnosis.md`](docs/diagnosis.md) for the full evidence trail.

## Kernel patch

The proposed upstream fix is:

```c
static const struct acpi_device_id i2c_acpi_force_100khz_device_ids[] = {
    { "DLL0945", 0 },
    { "ELAN0678", 0 },
    { "ELAN06FA", 0 },
    { "ELAN1200", 0 },
    { "ELAN1300", 0 },
    {}
};
```

The patch is in
[`patches/0001-i2c-acpi-add-ELAN1200-to-100khz-quirk.patch`](patches/0001-i2c-acpi-add-ELAN1200-to-100khz-quirk.patch).
It targets current `torvalds/linux` master. Kernel 6.18.y has a shorter list,
so the patch must be rebased before applying it to older stable trees.

See [`patches/README.md`](patches/README.md) for apply and submission
instructions. The kernel patch is a proposal and has not been merged upstream.
The DSDT override is the verified fix.

## Other machines and distributions

The scripts are intentionally specific to the X571GD. The procedure is
distro-independent, but the ASL names and DSDT layout are not.

- If your touchpad is already `ELAN06FA`, `ELAN0678`, or `ELAN1300`, try a
  current kernel first; the quirk may already be present.
- If your touchpad has a different ACPI ID, inspect its `TPD0` block and adapt
  the ASL patch. Do not run this tool on another model and assume it patched
  the right device.
- For bootloader and initramfs details, see
  [`docs/other-distros.md`](docs/other-distros.md).

## Repository layout

```text
.
├── docs/                  diagnosis, distribution notes, verification, troubleshooting
├── examples/              bootloader examples
├── patches/               upstream kernel quirk patch
├── scripts/               ASL patch, AML validation, cpio builder, runtime check
├── tests/                 dependency-free Python tests
├── CHANGELOG.md
├── LICENSE
└── Makefile
```

## Development checks

```bash
make check
```

This runs Python syntax checks, the unit tests, shell syntax checks, and the
sanitization check. If `shellcheck` is installed, it also lints the shell
scripts. The GitHub Actions workflow runs the same target on Ubuntu.

## Rollback

Boot the normal GRUB entry. The override is only loaded by the entry that lists
`acpi-fix.cpio`; it does not modify the firmware. To remove it completely:

```bash
sudo rm -f /boot/acpi-fix.cpio /boot/grub/custom.cfg
```

If you added the entry to `/etc/grub.d/40_custom`, remove it there and
regenerate `grub.cfg`.

## Troubleshooting

- The override did not load: check that `acpi-fix.cpio` is before the normal
  initramfs and that the boot entry is actually selected.
- The active DSDT size is still 264082: the cpio path is wrong, the cpio is
  compressed, or the kernel rejected the table.
- Secure Boot is enabled: the kernel will not accept an unsigned ACPI override.
- `iasl` reports errors: use `-f -sa`, and check that the AML was produced.
- The touchpad is still unstable: verify the active DSDT size before changing
  anything else.

More detail is in [`docs/troubleshooting.md`](docs/troubleshooting.md).

## References

- Linux kernel `drivers/i2c/i2c-core-acpi.c`
- Linux kernel `drivers/acpi/tables.c`
- [ACPICA tools](https://www.acpica.org/)
- [Arch Wiki: DSDT](https://wiki.archlinux.org/title/DSDT)
- [libinput touchpad jumping](https://wayland.freedesktop.org/libinput/doc/latest/touchpad-jumping-cursors.html)
- ELAN06FA quirk: Linux commit `bfd74cd1fbc026f04446e67d6915c7e199c2bffd`
- ELAN0678 quirk: Linux commit `9998e388be9930c106eb5904c23ecf2162407527`
- ELAN1300 quirk: Linux commit `9e9762e578db7556bea644bb5a8a2435f63544d1`

## License

Copyright (C) 2026 Rayuga.

This repository is licensed under the GNU General Public License, version 2
only (`GPL-2.0-only`). See [`LICENSE`](LICENSE). The kernel patch is intended
for the Linux kernel and is provided under the same license.

## Disclaimer

ACPI table overrides can prevent a machine from booting. Keep a known-good
boot entry and a backup of your working configuration. This project is not
affiliated with ASUS, ELAN, or the Linux kernel maintainers. Use at your own
risk.
