from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import patch_dsdt  # noqa: E402


def sample_dsdt(*, hid: str = "ELAN1200", with_tpds: bool = True) -> str:
    speed_branches = ""
    if with_tpds:
        speed_branches = """\
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
"""
    return f"""\
DefinitionBlock ("", "DSDT", 2, "TESTID", "TESTTBL0", 0x01072009)
{{
    Scope (\\_SB)
    {{
        Device (PCI0)
        {{
            Device (I2C0)
            {{
                Device (TPD0)
                {{
                    Name (SBFB, Buffer (0x19)
                    {{
                        /* 0000 */  0x8E, 0x14, 0x00, 0x01, 0x00, 0x01, 0x02, 0x00,
                        /* 0008 */  0x00, 0x01, 0x06, 0x00, 0x80, 0x1A, 0x06, 0x00,
                        /* 0010 */  0x00, 0x00, 0x4E, 0x55, 0x4C, 0x4C, 0x00, 0x79,
                        /* 0018 */  0x00
                    }})
                    Name (_HID, "{hid}")
                    Method (_INI, 0, NotSerialized)
                    {{
                        If ((TPDT == 0x05))
                        {{
                            _HID = "{hid}"
                            HID2 = TPDH
                            BADR = TPDB
{speed_branches}                            Return (Zero)
                        }}
                    }}
                }}
            }}
        }}
    }}
}}
"""


class PatchTextTests(unittest.TestCase):
    def test_patches_speed_and_revision(self) -> None:
        patched, result = patch_dsdt.patch_text(sample_dsdt())

        self.assertTrue(result.changed)
        self.assertEqual(result.old_revision, 0x01072009)
        self.assertEqual(result.new_revision, 0x0107200A)
        self.assertEqual(result.device_count, 1)
        self.assertIn("SPED = 0x000186A0", patched)
        self.assertIn("0xA0, 0x86, 0x01, 0x00", patched)
        self.assertNotIn("TPDS == One", patched)
        self.assertNotIn("0x00061A80", patched)
        self.assertIn("0x0107200A", patched)

    def test_is_idempotent(self) -> None:
        once, _ = patch_dsdt.patch_text(sample_dsdt())
        twice, result = patch_dsdt.patch_text(once)

        self.assertFalse(result.changed)
        self.assertEqual(twice, once)

    def test_rejects_non_elan_device(self) -> None:
        text = sample_dsdt(hid="SYNA2393")
        with self.assertRaisesRegex(patch_dsdt.PatchError, "ELAN1200"):
            patch_dsdt.patch_text(text)

    def test_rejects_missing_speed_branches(self) -> None:
        text = sample_dsdt(with_tpds=False)
        with self.assertRaisesRegex(patch_dsdt.PatchError, "TPDS"):
            patch_dsdt.patch_text(text)

    def test_only_first_matching_device_is_patched(self) -> None:
        text = sample_dsdt()
        second = text.split("DefinitionBlock", 1)[1]
        text = text + "\n" + "DefinitionBlock" + second
        _, result = patch_dsdt.patch_text(text)
        self.assertEqual(result.device_count, 2)


class CliTests(unittest.TestCase):
    def test_writes_output_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "dsdt.dsl"
            output = Path(tmp) / "dsdt-patched.dsl"
            source.write_text(sample_dsdt())

            first = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "patch_dsdt.py"),
                    str(source),
                    "-o",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue(output.exists())

            second = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "patch_dsdt.py"),
                    str(source),
                    "-o",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(second.returncode, 1)
            self.assertIn("output exists", second.stderr)

            check = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "patch_dsdt.py"),
                    "--check",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertIn("already patched", check.stdout)


if __name__ == "__main__":
    unittest.main()
