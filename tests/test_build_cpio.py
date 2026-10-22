from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build-cpio.sh"


def make_dsdt() -> bytes:
    data = bytearray(36)
    data[0:4] = b"DSDT"
    struct.pack_into("<I", data, 4, 36)
    data[8] = 2
    data[10:16] = b"TESTID"
    data[16:24] = b"TESTTBL0"
    struct.pack_into("<I", data, 24, 0x0107200A)
    data[28:32] = b"INTL"
    struct.pack_into("<I", data, 32, 0x20260408)
    data[9] = (-sum(data)) & 0xFF
    return bytes(data)


@unittest.skipUnless(shutil.which("cpio"), "cpio is not installed")
class BuildCpioTests(unittest.TestCase):
    def test_builds_archive_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            aml = work / "DSDT.aml"
            archive = work / "acpi-fix.cpio"
            aml.write_bytes(make_dsdt())

            first = subprocess.run(
                ["sh", str(BUILD_SCRIPT), "-o", str(archive), str(aml)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue(archive.exists())

            with archive.open("rb") as handle:
                listing = subprocess.run(
                    ["cpio", "-it"],
                    stdin=handle,
                    check=False,
                    capture_output=True,
                    text=True,
                )
            self.assertEqual(listing.returncode, 0, listing.stderr)
            self.assertIn(
                "kernel/firmware/acpi/DSDT.aml", listing.stdout
            )

            second = subprocess.run(
                ["sh", str(BUILD_SCRIPT), "-o", str(archive), str(aml)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(second.returncode, 1)
            self.assertIn("output exists", second.stderr)

            third = subprocess.run(
                ["sh", str(BUILD_SCRIPT), "-f", "-o", str(archive), str(aml)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(third.returncode, 0, third.stderr)

            collision = subprocess.run(
                ["sh", str(BUILD_SCRIPT), "-f", "-o", str(aml), str(aml)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(collision.returncode, 1)
            self.assertIn("must differ", collision.stderr)
            self.assertEqual(aml.read_bytes(), make_dsdt())

            extract = work / "extract"
            extract.mkdir()
            with archive.open("rb") as handle:
                unpack = subprocess.run(
                    ["cpio", "-id"],
                    cwd=extract,
                    stdin=handle,
                    check=False,
                    capture_output=True,
                    text=True,
                )
            self.assertEqual(unpack.returncode, 0, unpack.stderr)
            extracted = extract / "kernel/firmware/acpi/DSDT.aml"
            self.assertEqual(extracted.read_bytes(), aml.read_bytes())


if __name__ == "__main__":
    unittest.main()
