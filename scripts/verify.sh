#!/bin/sh
set -eu

EXPECTED_SIZE=${EXPECTED_SIZE:-263792}
DSDT=/sys/firmware/acpi/tables/DSDT

case "$EXPECTED_SIZE" in
    *[!0-9]*)
        echo "error: EXPECTED_SIZE must be a number" >&2
        exit 2
        ;;
esac

printf 'kernel: %s\n' "$(uname -r)"

if [ ! -e "$DSDT" ]; then
    echo "error: $DSDT not found" >&2
    exit 1
fi

SIZE=
if [ -r "$DSDT" ]; then
    SIZE=$(wc -c < "$DSDT" | tr -d '[:space:]')
fi
if [ -z "$SIZE" ]; then
    SIZE=$(stat -c '%s' "$DSDT" 2>/dev/null ||
        stat -f '%z' "$DSDT" 2>/dev/null || true)
fi
if [ -z "$SIZE" ]; then
    echo "error: cannot determine the size of $DSDT" >&2
    exit 1
fi

printf 'active DSDT: %s bytes (expected %s)\n' "$SIZE" "$EXPECTED_SIZE"

if [ "$SIZE" -ne "$EXPECTED_SIZE" ]; then
    echo "FAIL: the ACPI override does not appear to be active." >&2
    echo "Boot the entry that loads acpi-fix.cpio before the initramfs." >&2
    exit 1
fi

cat <<'EOF'

PASS: the active DSDT has the expected patched size.

Confirm the kernel accepted the override:

  sudo dmesg | grep -iE 'ACPI table found in initrd|Table Upgrade'

Manual charger test:

  sudo libinput debug-events --device /dev/input/event8

Adjust the event number if needed. Use the touchpad for several minutes
with the charger connected and look for "Touch jump detected and discarded".
EOF
