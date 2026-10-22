#!/usr/bin/env python3
"""Patch an ASUS VivoBook X571GD DSDT for the ELAN1200 touchpad.

The X571GD DSDT gives the ELAN1200 I2C bus a 400 kHz speed. Charger noise
makes the ELAN firmware apply excessive smoothing at that speed. This tool
rewrites the active ``Device (TPD0)`` block so the bus is always described
as 100 kHz, and bumps the DSDT OEM revision so the kernel accepts the table
as an initrd override.

The tool is deliberately strict: it only recognizes the X571GD layout
(``TPD0`` + ``ELAN1200`` + ``SBFB`` + ``TPDS``). It refuses to guess on an
unknown DSDT. Review the diff before compiling the result.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

HUNDRED_KHZ = 0x000186A0
FOUR_HUNDRED_KHZ = 0x00061A80
ONE_MHZ = 0x000F4240
TARGET_HID = "ELAN1200"
TARGET_DEVICE = "TPD0"


class PatchError(RuntimeError):
    """Raised when the DSDT does not have the expected X571GD layout."""


@dataclass(frozen=True)
class PatchResult:
    changed: bool
    old_revision: int
    new_revision: int
    device_count: int


def _skip_string(text: str, index: int) -> int:
    if text[index] != '"':
        raise PatchError(f"expected a string at offset {index}")
    index += 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == '"':
            return index + 1
        index += 1
    raise PatchError("unterminated string in ASL")


def _skip_comment(text: str, index: int) -> int | None:
    if text.startswith("//", index):
        end = text.find("\n", index)
        return len(text) if end == -1 else end + 1
    if text.startswith("/*", index):
        end = text.find("*/", index + 2)
        if end == -1:
            raise PatchError("unterminated block comment in ASL")
        return end + 2
    return None


def _find_open_brace(text: str, start: int, end: int | None = None) -> int:
    limit = len(text) if end is None else end
    index = start
    while index < limit:
        char = text[index]
        if char == '"':
            index = _skip_string(text, index)
            continue
        if char == "/" and index + 1 < limit and text[index + 1] in "/*":
            skipped = _skip_comment(text, index)
            if skipped is not None:
                index = skipped
                continue
        if char == "{":
            return index
        index += 1
    raise PatchError("opening brace not found in ASL")


def find_matching_brace(text: str, open_index: int) -> int:
    """Return the index just after the brace matching ``open_index``."""
    if open_index >= len(text) or text[open_index] != "{":
        raise PatchError(f"expected '{{' at offset {open_index}")
    depth = 0
    index = open_index
    while index < len(text):
        char = text[index]
        if char == '"':
            index = _skip_string(text, index)
            continue
        if char == "/" and index + 1 < len(text) and text[index + 1] in "/*":
            skipped = _skip_comment(text, index)
            if skipped is not None:
                index = skipped
                continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    raise PatchError("unbalanced braces in ASL")


def _device_blocks(text: str) -> list[tuple[int, int]]:
    pattern = re.compile(
        rf"^[ \t]*Device\s*\(\s*{re.escape(TARGET_DEVICE)}\s*\)",
        re.MULTILINE,
    )
    blocks: list[tuple[int, int]] = []
    for match in pattern.finditer(text):
        open_brace = _find_open_brace(text, match.end())
        blocks.append((match.start(), find_matching_brace(text, open_brace)))
    return blocks


def _elan_blocks(text: str) -> list[tuple[int, int]]:
    matches: list[tuple[int, int]] = []
    for start, end in _device_blocks(text):
        block = text[start:end]
        has_assignment = re.search(
            rf'_HID\s*=\s*"{re.escape(TARGET_HID)}"', block
        )
        has_name = re.search(
            rf'Name\s*\(\s*_HID\s*,\s*"{re.escape(TARGET_HID)}"', block
        )
        if has_assignment or has_name:
            matches.append((start, end))
    return matches


def _tpdt_branch(block: str) -> tuple[int, int]:
    pattern = re.compile(
        r"^[ \t]*If\s*\(\(TPDT\s*==\s*0x0?5\)\)\s*(?://.*)?$",
        re.MULTILINE,
    )
    match = pattern.search(block)
    if not match:
        raise PatchError("If ((TPDT == 0x05)) branch not found")
    open_brace = _find_open_brace(block, match.end())
    end = find_matching_brace(block, open_brace)
    return match.start(), end


def _tpds_value(raw: str) -> int:
    value = raw.strip().lower()
    if value == "zero":
        return 0
    if value == "one":
        return 1
    if value in ("0x02", "0x2"):
        return 2
    raise PatchError(f"unexpected TPDS value: {raw!r}")


def _replace_speed_chain(
    block: str, branch_start: int, branch_end: int
) -> tuple[str, bool]:
    branch = block[branch_start:branch_end]
    pattern = re.compile(
        r"^([ \t]*)If\s*\(\(TPDS\s*==\s*(Zero|One|0x0?2)\)\)\s*(?://.*)?$",
        re.MULTILINE | re.IGNORECASE,
    )
    matches = list(pattern.finditer(branch))
    if not matches:
        already_patched = re.search(
            r"^[ \t]*SPED\s*=\s*0x000186A0\s*$", branch, re.MULTILINE
        )
        if already_patched and "TPDS ==" not in branch:
            return block, False
        raise PatchError("no TPDS speed branches found")

    values = [_tpds_value(match.group(2)) for match in matches]
    if values != [0, 1, 2]:
        raise PatchError(
            "expected TPDS speed branches 0, 1, 2 in order; "
            f"found {values}"
        )

    block_ends: list[int] = []
    for match in matches:
        open_brace = _find_open_brace(branch, match.end())
        block_ends.append(find_matching_brace(branch, open_brace))

    span_start = matches[0].start()
    span_end = block_ends[-1]
    speed_indent = matches[0].group(1)
    tail = branch[span_end:].lstrip("\n")
    replacement = f"{speed_indent}SPED = 0x{HUNDRED_KHZ:08X}\n\n"
    new_branch = branch[:span_start] + replacement + tail
    new_block = block[:branch_start] + new_branch + block[branch_end:]

    if new_block.count("TPDS ==") != block.count("TPDS ==") - 3:
        raise PatchError("could not remove all three TPDS speed branches")
    if "SPED = 0x000186A0" not in new_block:
        raise PatchError("100 kHz SPED assignment was not written")
    return new_block, new_block != block


def _replace_sbfb(block: str) -> tuple[str, bool]:
    match = re.search(r"Name\s*\(\s*SBFB\s*,\s*Buffer\s*\(", block)
    if not match:
        raise PatchError("SBFB buffer not found")
    open_brace = _find_open_brace(block, match.end())
    end = find_matching_brace(block, open_brace)
    buffer = block[open_brace:end]

    if re.search(r"0xA0,\s*0x86,\s*0x01,\s*0x00", buffer):
        return block, False

    new_buffer, count = re.subn(
        r"0x80,\s*0x1A,\s*0x06,\s*0x00",
        "0xA0, 0x86, 0x01, 0x00",
        buffer,
        count=1,
    )
    if count != 1:
        raise PatchError("400 kHz SBFB bytes (80 1A 06 00) not found")
    new_block = block[:open_brace] + new_buffer + block[end:]
    return new_block, True


_REVISION_PATTERN = re.compile(
    r"^[ \t]*(DefinitionBlock\s*\(.*?,\s*)(0x[0-9A-Fa-f]{1,8})"
    r"(\s*\)(?:\s*//.*)?\s*)$",
    re.MULTILINE,
)


def _read_revision(text: str) -> int:
    match = _REVISION_PATTERN.search(text)
    if not match:
        raise PatchError("DefinitionBlock header not found")
    return int(match.group(2), 16)


def _bump_revision(text: str) -> tuple[str, int, int]:
    match = _REVISION_PATTERN.search(text)
    if not match:
        raise PatchError("DefinitionBlock header not found")
    old_revision = int(match.group(2), 16)
    new_revision = old_revision + 1
    if new_revision > 0xFFFFFFFF:
        raise PatchError("OEM revision overflow")
    new_text = (
        text[: match.start(2)]
        + f"0x{new_revision:08X}"
        + text[match.end(2):]
    )
    return new_text, old_revision, new_revision


def patch_text(text: str) -> tuple[str, PatchResult]:
    """Patch an X571GD DSDT source and return the result and a summary."""
    matching_devices = _elan_blocks(text)
    if not matching_devices:
        raise PatchError(
            'no Device (TPD0) with _HID "ELAN1200" found; '
            "this tool only supports the X571GD layout"
        )

    start, end = matching_devices[0]
    block = text[start:end]

    branch_start, branch_end = _tpdt_branch(block)
    new_block, speed_changed = _replace_speed_chain(
        block, branch_start, branch_end
    )
    new_block, sbfb_changed = _replace_sbfb(new_block)
    changed = speed_changed or sbfb_changed

    old_revision = _read_revision(text)
    if changed:
        text = text[:start] + new_block + text[end:]
        text, old_revision, new_revision = _bump_revision(text)
    else:
        new_revision = old_revision

    return text, PatchResult(
        changed=changed,
        old_revision=old_revision,
        new_revision=new_revision,
        device_count=len(matching_devices),
    )


def _unified_diff(before: str, after: str, input_path: Path, output: Path) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(input_path),
            tofile=str(output),
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Patch an ASUS VivoBook X571GD DSDT so the ELAN1200 I2C "
            "bus is described as 100 kHz."
        )
    )
    parser.add_argument("input", type=Path, help="decompiled DSDT .dsl")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output path (default: <input>-patched.dsl)",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="overwrite an existing output file",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 0 if already patched, 1 if it needs patching",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="print a unified diff of the change",
    )
    args = parser.parse_args(argv)

    try:
        before = args.input.read_text()
    except OSError as exc:
        print(f"error: cannot read {args.input}: {exc}", file=sys.stderr)
        return 1

    try:
        after, result = patch_text(before)
    except PatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if result.device_count > 1:
        print(
            f"warning: {result.device_count} TPD0 blocks contain "
            f"{TARGET_HID}; patching the first one",
            file=sys.stderr,
        )

    if args.check:
        if result.changed:
            print("needs patching")
            return 1
        print("already patched")
        return 0

    if not result.changed:
        print("already patched; nothing to do")
        return 0

    output = args.output or args.input.with_name(
        f"{args.input.stem}-patched{args.input.suffix}"
    )
    if output.resolve() == args.input.resolve():
        print("error: output must differ from input", file=sys.stderr)
        return 1
    if output.exists() and not args.force:
        print(
            f"error: output exists: {output} (use --force to overwrite)",
            file=sys.stderr,
        )
        return 1

    if args.diff:
        print(_unified_diff(before, after, args.input, output), end="")

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
        )
        try:
            with os.fdopen(descriptor, "w") as handle:
                handle.write(after)
            os.replace(temporary, output)
        except BaseException:
            os.unlink(temporary)
            raise
    except OSError as exc:
        print(f"error: cannot write {output}: {exc}", file=sys.stderr)
        return 1

    print(f"patched {args.input} -> {output}")
    print(
        "OEM revision: "
        f"0x{result.old_revision:08X} -> 0x{result.new_revision:08X}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
