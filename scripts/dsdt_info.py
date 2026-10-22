#!/usr/bin/env python3
"""Inspect and validate an ACPI DSDT AML file.

The kernel's initrd ACPI table override only accepts a table when the
header length matches the file size and the checksum is zero. This script
checks those conditions before the file is packed into an initrd cpio.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ACPI_HEADER_SIZE = 36


class DsdtError(ValueError):
    """Raised when a file is not a valid ACPI DSDT."""


@dataclass(frozen=True)
class DsdtInfo:
    path: str
    size: int
    signature: str
    length: int
    revision: int
    checksum: int
    oem_id: str
    oem_table_id: str
    oem_revision: int
    compiler_id: str
    compiler_version: int


def _text(raw: bytes) -> str:
    return raw.decode("ascii", errors="replace").rstrip("\x00 ")


def parse_dsdt(data: bytes, path: str = "<memory>") -> DsdtInfo:
    if len(data) < ACPI_HEADER_SIZE:
        raise DsdtError(
            f"{path}: file is too small for an ACPI header "
            f"({len(data)} bytes, need at least {ACPI_HEADER_SIZE})"
        )

    signature = _text(data[0:4])
    length = struct.unpack_from("<I", data, 4)[0]
    revision = data[8]
    checksum = data[9]
    oem_id = _text(data[10:16])
    oem_table_id = _text(data[16:24])
    oem_revision = struct.unpack_from("<I", data, 24)[0]
    compiler_id = _text(data[28:32])
    compiler_version = struct.unpack_from("<I", data, 32)[0]

    if signature != "DSDT":
        raise DsdtError(
            f"{path}: unexpected signature {signature!r}, expected 'DSDT'"
        )
    if length != len(data):
        raise DsdtError(
            f"{path}: header length {length} does not match file size "
            f"{len(data)}"
        )
    if sum(data) % 256 != 0:
        raise DsdtError(
            f"{path}: bad ACPI checksum (sum mod 256 = {sum(data) % 256})"
        )

    return DsdtInfo(
        path=path,
        size=len(data),
        signature=signature,
        length=length,
        revision=revision,
        checksum=checksum,
        oem_id=oem_id,
        oem_table_id=oem_table_id,
        oem_revision=oem_revision,
        compiler_id=compiler_id,
        compiler_version=compiler_version,
    )


def parse_file(path: Path) -> DsdtInfo:
    return parse_dsdt(path.read_bytes(), str(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect and validate an ACPI DSDT AML file."
    )
    parser.add_argument("aml", type=Path, help="path to a DSDT .aml file")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing on success"
    )
    args = parser.parse_args(argv)

    try:
        info = parse_file(args.aml)
    except (OSError, DsdtError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        if args.json:
            print(json.dumps(asdict(info), indent=2))
        else:
            print(f"file:             {info.path}")
            print(f"size:             {info.size} bytes")
            print(f"signature:        {info.signature}")
            print(f"header length:    {info.length}")
            print(f"ACPI revision:    {info.revision}")
            print(f"checksum:         0x{info.checksum:02X} (valid)")
            print(f"OEM ID:           {info.oem_id}")
            print(f"OEM table ID:     {info.oem_table_id}")
            print(f"OEM revision:     0x{info.oem_revision:08X}")
            print(f"compiler ID:      {info.compiler_id}")
            print(f"compiler version: 0x{info.compiler_version:08X}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
