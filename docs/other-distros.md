# Other distributions and bootloaders

The fix is distro-independent. The X571GD-specific part is the ASL patch; the
packaging, initramfs, and bootloader steps vary by distribution.

> The scripts in this repository target the X571GD DSDT layout. Do not assume
> they are safe for another laptop. See the main [README](../README.md) for the
> verified configuration.

## 1. Install the tools

You need a package that provides `acpidump`, `acpixtract`, and `iasl`, plus
`cpio` and Python 3.

| Distribution | Typical packages |
|---|---|
| Void Linux | `acpica-utils`, `cpio`, `python3` |
| Arch Linux | `acpica`, `cpio`, `python` |
| Debian / Ubuntu | `acpica-tools`, `cpio`, `python3` |
| Fedora | `acpica-tools`, `cpio`, `python3` |
| openSUSE | `acpica`, `cpio`, `python3` |
| Alpine | the `acpica` package for your release, `cpio`, `python3` |
| NixOS | `nix-shell -p acpica cpio python3` |

If a package name has changed, install the package that provides `iasl` and
`acpidump`. The exact package name is not important.

## 2. Check kernel support

The kernel must have ACPI table upgrade support:

```bash
grep -E '^CONFIG_ACPI_TABLE_UPGRADE=' /boot/config-"$(uname -r)"
# or
zgrep -E '^CONFIG_ACPI_TABLE_UPGRADE=' /proc/config.gz
```

Expected:

```text
CONFIG_ACPI_TABLE_UPGRADE=y
```

If the option is missing or disabled, the override cpio will be ignored. Use a
kernel built with the option enabled, or use the kernel quirk patch instead.

## 3. Check Secure Boot and lockdown

An unsigned ACPI override is rejected when the kernel is locked down.

```bash
mokutil --sb-state 2>/dev/null || true
cat /sys/kernel/security/lockdown 2>/dev/null || true
```

If Secure Boot is enabled or lockdown is `integrity` or `confidentiality`,
either:

- disable Secure Boot for this boot entry, or
- sign the kernel and initramfs (or UKI) with your own key and enroll it.

The verified machine used Secure Boot disabled. Do not disable Secure Boot
permanently without understanding the security trade-off.

## 4. Dump, patch, compile, and pack

These steps are the same on every distribution. Run them from the repository
root.

```bash
mkdir -p work
cd work

sudo acpidump > acpidump.txt
acpixtract -a acpidump.txt
iasl -d dsdt.dat

python3 ../scripts/patch_dsdt.py dsdt.dsl \
    -o dsdt-patched.dsl --diff

iasl -f -sa dsdt-patched.dsl

python3 ../scripts/dsdt_info.py dsdt-patched.aml

../scripts/build-cpio.sh -o acpi-fix.cpio dsdt-patched.aml
cd ..
```

The final cpio must contain:

```text
kernel/firmware/acpi/DSDT.aml
```

Do not compress it with gzip, xz, or zstd. The kernel's ACPI scanner expects an
uncompressed `newc` cpio.

## 5. Install the cpio

Copy the cpio somewhere your bootloader can read it **before** the normal
initramfs. On many distributions `/boot` is a suitable location:

```bash
sudo install -m 0644 work/acpi-fix.cpio /boot/acpi-fix.cpio
```

On systemd-boot with a separate EFI System Partition, copy it to the ESP
instead:

```bash
sudo install -m 0644 work/acpi-fix.cpio /boot/efi/acpi-fix.cpio
```

Use the path that matches your bootloader configuration. The file must remain
readable by the bootloader.

## 6. Add a boot entry

Keep the normal entry untouched and add a separate entry for testing. This
makes rollback as simple as selecting the normal entry.

### GRUB

Most distributions source `/boot/grub/custom.cfg` from `41_custom`. Copy the
example and edit the placeholders:

```bash
sudo install -m 0644 examples/custom.cfg.example /boot/grub/custom.cfg
sudoedit /boot/grub/custom.cfg
```

```grub
menuentry "Linux (ELAN1200 100 kHz DSDT fix)" {
    linux /boot/vmlinuz-6.18.58_1 root=UUID=<YOUR-ROOT-UUID> ro loglevel=4
    initrd /boot/acpi-fix.cpio /boot/initramfs-6.18.58_1.img
}
```

The cpio must come first in the `initrd` line. If your GRUB configuration does
not include `custom.cfg`, add the same entry to `/etc/grub.d/40_custom` and run
your distribution's `grub-mkconfig` command.

Useful checks:

```bash
sudo grep -n 'custom.cfg' /boot/grub/grub.cfg
sudo grub-script-check /boot/grub/custom.cfg
```

### systemd-boot

systemd-boot reads entries from the `loader/entries` directory on the ESP.
Paths in the entry are relative to the ESP, not to `/boot`.

Example `/boot/efi/loader/entries/elan1200-fix.conf`:

```ini
title   Linux (ELAN1200 100 kHz DSDT fix)
linux   /vmlinuz-linux
initrd  /acpi-fix.cpio
initrd  /initramfs-linux.img
options root=UUID=<YOUR-ROOT-UUID> rw
```

Install the cpio on the ESP:

```bash
sudo install -m 0644 work/acpi-fix.cpio /boot/efi/acpi-fix.cpio
```

Check the entry list with:

```bash
bootctl list
```

### Unified Kernel Image (UKI)

If you boot a UKI, the override cpio must be part of the image, before the
normal initramfs. Build a combined initrd and pass it to your UKI tool:

```bash
cat acpi-fix.cpio /boot/initramfs-linux.img > /tmp/combined-initrd.img
```

Then rebuild the UKI with your normal command, using
`/tmp/combined-initrd.img` as the initrd. Re-sign the UKI if Secure Boot is
enabled. The exact `ukify`, `dracut`, or `mkinitcpio` invocation depends on
your distribution.

### NixOS

NixOS can prepend the cpio to the initrd directly:

```nix
boot.initrd.prepend = [ "${./acpi-fix.cpio}" ];
```

Place `acpi-fix.cpio` next to the NixOS configuration file, or use an absolute
path in the Nix store. Rebuild with `nixos-rebuild switch` and reboot. This
works with the standard NixOS initrd generation; the ACPI scanner sees the
prepended cpio before the normal initramfs.

## 7. Reboot and verify

Select the new entry. Then:

```bash
uname -r
stat -c '%s' /sys/firmware/acpi/tables/DSDT
sudo dmesg | grep -iE 'ACPI table found in initrd|Table Upgrade'
```

Expected for the verified X571GD:

```text
6.18.58_1
263792
ACPI: Table Upgrade: install [DSDT-_ASUS_-Notebook]
```

The repository's helper checks the size:

```bash
./scripts/verify.sh
```

The original table is 264082 bytes; the patched table is 263792 bytes. If the
size is still 264082, the override was not loaded.

## 8. Rollback

Boot the normal entry. The firmware is untouched. To remove the override:

```bash
sudo rm -f /boot/acpi-fix.cpio /boot/grub/custom.cfg
```

If you used a systemd-boot entry, remove its `.conf` file and the cpio from the
ESP. If you used a UKI, rebuild it without the prepended cpio. If you edited
`/etc/grub.d/40_custom`, remove the entry and regenerate `grub.cfg`.

## Notes for specific initramfs tools

- **dracut**: the override is a separate cpio. You do not need to add it to the
  host initramfs; list it before the host initramfs in the bootloader.
- **mkinitcpio**: the same applies. Keep the override separate so a kernel
  update does not silently drop it; update the entry's kernel and initramfs
  paths after an upgrade.
- **initramfs-tools (Debian/Ubuntu)**: same approach. The override cpio is not
  managed by `update-initramfs`.
- **NixOS**: use `boot.initrd.prepend` as shown above so the cpio is part of
  the generated initrd.

After a kernel update, the boot entry still points at the old kernel and
initramfs unless you update it. Either edit the entry or generate it from your
bootloader's normal configuration. The override cpio itself does not need to be
rebuilt when the kernel changes.
