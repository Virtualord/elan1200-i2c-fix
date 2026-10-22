# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-22

### Added

- Verified 100 kHz DSDT override for the ASUS VivoBook X571GD ELAN1200
  touchpad.
- `patch_dsdt.py` to apply the X571GD ASL patch.
- `dsdt_info.py` to inspect and validate ACPI DSDT headers.
- `build-cpio.sh` to validate and pack a DSDT override cpio.
- `verify.sh` to check the active DSDT size after reboot.
- A GRUB `custom.cfg` example.
- An upstream kernel quirk patch adding `ELAN1200` to the 100 kHz device
  list.
- Documentation for diagnosis, other distributions, verification, and
  troubleshooting.
- A hardware-report issue template, README status badges, and a 1280x640
  social preview image.

[1.0.0]: https://github.com/Virtualord/elan1200-i2c-fix/releases/tag/v1.0.0
