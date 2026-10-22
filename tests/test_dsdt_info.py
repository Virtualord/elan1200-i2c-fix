from __future__ import annotations

import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import dsdt_info  # noqa: E402


def make_dsdt(
    *,
    signature: bytes = b"DSDT",
    length: int = 36,
    oem_id: bytes = b"TESTID",
    oem_table_id: bytes = b"TESTTBL0",
    oem_revision: int = 0x0107200A,
    compiler_id: bytes = b"INTL",
    compiler_version: int = 0x20260408,
    corrupt_checksum: bool = False,
) -> bytes:
    data = bytearray(36)
    data[0:4] = signature
    struct.pack_into("<I", data, 4, length)
    data[8] = 2
    data[10:16] = oem_id
    data[16:24] = oem_table_id
    struct.pack_into("<I", data, 24, oem_revision)
    data[28:32] = compiler_id
    struct.pack_into("<I", data, 32, compiler_version)
    data[9] = (-sum(data)) & 0xFF
    if corrupt_checksum:
        data[9] = (data[9] + 1) & 0xFF
    return bytes(data)


class ParseDsdtTests(unittest.TestCase):
    def test_valid_header(self) -> None:
        info = dsdt_info.parse_dsdt(make_dsdt(), "test.aml")
        self.assertEqual(info.signature, "DSDT")
        self.assertEqual(info.length, 36)
        self.assertEqual(info.size, 36)
        self.assertEqual(info.oem_id, "TESTID")
        self.assertEqual(info.oem_table_id, "TESTTBL0")
        self.assertEqual(info.oem_revision, 0x0107200A)
        self.assertEqual(info.compiler_id, "INTL")
        self.assertEqual(info.compiler_version, 0x20260408)
        self.assertEqual(info.checksum, make_dsdt()[9])
        self.assertEqual(sum(make_dsdt()) % 256, 0)

    def test_rejects_bad_signature(self) -> None:
        with self.assertRaisesRegex(dsdt_info.DsdtError, "signature"):
            dsdt_info.parse_dsdt(make_dsdt(signature=b"SSDT"), "test.aml")

    def test_rejects_length_mismatch(self) -> None:
        with self.assertRaisesRegex(dsdt_info.DsdtError, "does not match"):
            dsdt_info.parse_dsdt(make_dsdt(length=40), "test.aml")

    def test_rejects_bad_checksum(self) -> None:
        with self.assertRaisesRegex(dsdt_info.DsdtError, "checksum"):
            dsdt_info.parse_dsdt(
                make_dsdt(corrupt_checksum=True), "test.aml"
            )

    def test_rejects_short_file(self) -> None:
        with self.assertRaisesRegex(dsdt_info.DsdtError, "too small"):
            dsdt_info.parse_dsdt(b"DSDT", "test.aml")


class CliTests(unittest.TestCase):
    def test_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "DSDT.aml"
            path.write_bytes(make_dsdt())
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "dsdt_info.py"),
                 "--json", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["signature"], "DSDT")
        self.assertEqual(payload["oem_revision"], 0x0107200A)

    def test_invalid_file_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "DSDT.aml"
            path.write_bytes(b"not a dsdt")
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "dsdt_info.py"),
                 str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
