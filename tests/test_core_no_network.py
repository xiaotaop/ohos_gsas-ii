"""Static evidence that the core never opens a network connection.

RELEASE_ACCEPTANCE row 4 asks for an explicitly offline device run. This test
does not replace that device evidence: it only proves the shipped core sources
contain no network API reference, so the computation path is offline by
construction. Any hit is a real finding, not a whitelist candidate.
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


class CoreHasNoNetworkDependencyTest(unittest.TestCase):
    def test_core_sources_reference_no_network_api(self):
        hits = []
        for root, patterns in SEARCH:
            for pattern in patterns:
                for path in root.rglob(pattern):
                    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                        if FORBIDDEN.search(line):
                            hits.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
        self.assertEqual(hits, [], "network API reference in core sources:\n" + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()