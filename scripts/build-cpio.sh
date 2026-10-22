#!/bin/sh
set -eu

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
OUTPUT=acpi-fix.cpio
FORCE=0

usage() {
    cat <<'EOF'
Usage: build-cpio.sh [-f] [-o OUTPUT] DSDT.aml

Validate a DSDT AML file and build an uncompressed initrd cpio containing
kernel/firmware/acpi/DSDT.aml. The kernel loads this cpio before the normal
initramfs to apply the ACPI table override.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        -f|--force)
            FORCE=1
            shift
            ;;
        -o|--output)
            [ $# -ge 2 ] || {
                echo "error: -o requires a value" >&2
                exit 2
            }
            OUTPUT=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "error: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
        *)
            break
            ;;
    esac
done

[ $# -eq 1 ] || {
    usage >&2
    exit 2
}

INPUT=$1

[ -f "$INPUT" ] || {
    echo "error: input not found: $INPUT" >&2
    exit 1
}
command -v cpio >/dev/null 2>&1 || {
    echo "error: cpio not found" >&2
    exit 1
}
command -v python3 >/dev/null 2>&1 || {
    echo "error: python3 not found" >&2
    exit 1
}

if [ -e "$OUTPUT" ] && [ "$FORCE" -ne 1 ]; then
    echo "error: output exists: $OUTPUT (use -f to overwrite)" >&2
    exit 1
fi

python3 "$SCRIPT_DIR/dsdt_info.py" --quiet "$INPUT"

WORKDIR=$(mktemp -d "${TMPDIR:-/tmp}/elan1200-cpio.XXXXXX")
cleanup() {
    rm -rf "$WORKDIR"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

mkdir -p "$WORKDIR/kernel/firmware/acpi"
cp "$INPUT" "$WORKDIR/kernel/firmware/acpi/DSDT.aml"

if ! (
    cd "$WORKDIR"
    find kernel -print0 | cpio -H newc -o --null
) > "$OUTPUT"; then
    rm -f "$OUTPUT"
    echo "error: cpio failed" >&2
    exit 1
fi

if ! cpio -it < "$OUTPUT" 2>/dev/null |
    grep -qx 'kernel/firmware/acpi/DSDT.aml'; then
    rm -f "$OUTPUT"
    echo "error: cpio does not contain kernel/firmware/acpi/DSDT.aml" >&2
    exit 1
fi

printf 'wrote %s (%s bytes)\n' "$OUTPUT" "$(wc -c < "$OUTPUT")"
cpio -it < "$OUTPUT"
