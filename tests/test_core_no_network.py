"""Check selected app sources for a small set of network API references.

RELEASE_ACCEPTANCE row 4 asks for an explicitly offline device run. This test
does not replace device evidence. It scans bridge, C++ and ETS source files for
the listed API patterns; it does not inspect the packaged Python runtime,
dynamic calls, or actual network traffic. A hit needs review, not a whitelist.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEARCH = (
    (ROOT / "bridge", ("*.py",)),
    (ROOT / "app/entry/src/main/cpp", ("*.cpp", "*.h")),
    (ROOT / "app/entry/src/main/ets", ("*.ets",)),
)
# Case-sensitive on purpose: PyErr_Fetch() must not count as fetch().
FORBIDDEN = re.compile(
    r"import\s+socket\b"
    r"|from\s+socket\b"
    r"|urllib\.request"
    r"|http\.client"
    r"|\brequests\."
    r"|@kit\.NetworkKit"
    r"|@ohos\.net\b"
    r"|net\.socket"
    r"|WebSocket"
    r"|\bfetch\(",
)


class ScannedAppSourcesNetworkReferenceTest(unittest.TestCase):
    def test_scanned_sources_reference_no_listed_network_api(self):
        hits = []
        for root, patterns in SEARCH:
            for pattern in patterns:
                for path in root.rglob(pattern):
                    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                        if FORBIDDEN.search(line):
                            hits.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
        self.assertEqual(hits, [], "listed network API reference in scanned sources:\n" + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()
