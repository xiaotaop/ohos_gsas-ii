"""Synthetic checks for the GSAS-II native-extension payload gate.

The gate protects the release path from a payload that passes the manifest and
hash gates while being unable to create a phase (no pyspg). Fixtures are
synthetic ELF headers, never real binaries or approval evidence.
"""
import importlib.util
import io
import json
import struct
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_gsas_native", ROOT / "scripts/payload/check_gsas_native.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def elf(machine=183, e_type=3):
    data = bytearray(64)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<HH", data, 16, e_type, machine)
    return bytes(data)


class PayloadGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.payload = Path(self.tmp.name)
        self.gsasii = self.payload / "runtime/lib/python3.12/site-packages/GSASII"
        self.gsasii.mkdir(parents=True)
        for name in gate.REQUIRED:
            self.write(name)

    def write(self, name, data=None, suffix="cpython-312-aarch64-linux-ohos.so"):
        (self.gsasii / f"{name}.{suffix}").write_bytes(elf() if data is None else data)

    def run_gate(self, *extra):
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate.main(["--payload", str(self.payload), *extra])
        return code, out.getvalue()

    def test_complete_payload_passes_and_writes_json(self):
        report = self.payload / "native.json"
        code, out = self.run_gate("--json", str(report))
        self.assertEqual(code, 0)
        self.assertIn("all 8 native extensions present", out)
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(data["releaseReady"])
        self.assertEqual(data["failures"], [])
        self.assertEqual(len(data["found"]), 8)

    def test_missing_pyspg_rejects_release_payload(self):
        (self.gsasii / "pyspg.cpython-312-aarch64-linux-ohos.so").unlink()
        code, out = self.run_gate()
        self.assertEqual(code, 2)
        self.assertIn("missing native extension: pyspg", out)
        self.assertIn("cannot create a phase", out)

    def test_allow_missing_downgrades_to_development_warning(self):
        (self.gsasii / "pyspg.cpython-312-aarch64-linux-ohos.so").unlink()
        code, out = self.run_gate("--allow-missing")
        self.assertEqual(code, 0)
        self.assertIn("DEV-ONLY", out)

    def test_foreign_architecture_is_rejected(self):
        (self.gsasii / "pypowder.cpython-312-aarch64-linux-ohos.so").unlink()
        self.write("pypowder", elf(machine=62))  # x86-64
        code, out = self.run_gate()
        self.assertEqual(code, 2)
        self.assertIn("not AArch64", out)

    def test_archive_instead_of_shared_object_is_rejected(self):
        (self.gsasii / "histogram2d.cpython-312-aarch64-linux-ohos.so").unlink()
        self.write("histogram2d", b"PK\x03\x04" + b"\0" * 60)
        code, out = self.run_gate()
        self.assertEqual(code, 2)
        self.assertIn("not an ELF file", out)

    def test_pydiffax_is_forbidden(self):
        self.write("pydiffax")
        code, out = self.run_gate()
        self.assertEqual(code, 2)
        self.assertIn("forbidden extension present", out)

    def test_missing_gsasii_directory_reports_code_3(self):
        self.gsasii.rename(self.gsasii.with_name("NOT_GSASII"))
        code, out = self.run_gate()
        self.assertEqual(code, 3)
        self.assertIn("not found", out)


if __name__ == "__main__":
    unittest.main()