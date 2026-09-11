"""A37/P16-001 secrets scan: scan git-tracked files for credential patterns.

Exit 1 when a real-looking secret is found. Known test fixtures (self-declared
marker 'METIS-TEST-SECRET') are reported but classified as expected triggers.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_pat": re.compile(r"ghp_[A-Za-z0-9]{36}"),
    "slack_token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "private_key_block": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "generic_api_key_assignment": re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*['\"]([A-Za-z0-9/+=_\-]{16,})['\"]"),
    "bearer": re.compile(r"Bearer\s+[A-Za-z0-9\-_.~+/]{25,}"),
}
ALLOWLIST_MARKERS = ("METIS-TEST-SECRET", "dummy", "example", "placeholder", "xxx")


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    files = []
    for line in out.stdout.splitlines():
        p = ROOT / line
        if p.is_file() and p.stat().st_size < 2_000_000:
            files.append(p)
    return files


def scan() -> tuple[list[dict], list[dict]]:
    findings: list[dict] = []
    expected: list[dict] = []
    for path in tracked_files():
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if ".env" in rel and not rel.endswith(".example"):
            findings.append({"file": rel, "rule": "env_file_committed", "match": rel})
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for rule, pattern in PATTERNS.items():
            for m in pattern.finditer(text):
                snippet = m.group(0)[:60]
                lowered = snippet.lower()
                if any(marker.lower() in lowered for marker in ALLOWLIST_MARKERS):
                    expected.append({"file": rel, "rule": rule, "match": snippet})
                else:
                    findings.append({"file": rel, "rule": rule, "match": snippet})
    return findings, expected


if __name__ == "__main__":
    findings, expected = scan()
    print(f"secrets scan: {len(findings)} findings, {len(expected)} expected test triggers")
    for f in findings:
        print(f"  [REAL] {f['rule']}: {f['file']} :: {f['match']}")
    for f in expected:
        print(f"  [TEST ] {f['rule']}: {f['file']} :: {f['match']}")
    sys.exit(1 if findings else 0)
