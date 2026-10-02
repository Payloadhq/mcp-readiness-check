#!/usr/bin/env python3
"""Tests for mcp-readiness-check/check.py.

Builds fixture manifests in temp dirs, runs check.py as a subprocess,
and asserts exit codes plus which RC-xxx checks fire.
Exit codes under test: 0 clean, 1 errors, 2 warnings-only.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

CHECK_PY = Path(__file__).resolve().parent.parent / "check.py"

VALID_MANIFEST = {
    "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
    "name": "io.github.payloadhq/test-server",
    "title": "Test Server",
    "description": "A test server used by the readiness-check test suite.",
    "version": "1.0.0",
    "license": "MIT",
    "repository": {
        "url": "https://github.com/payloadhq/test-server",
        "source": "github",
    },
    "packages": [
        {
            "registryType": "pypi",
            "identifier": "test-server",
            "version": "1.0.0",
            "transport": {"type": "stdio"},
        }
    ],
}

GOOD_README = "# Test Server\n\n## Install\n\npip install test-server\n\n## Usage\n\nRun it.\n"
BARE_README = "# Test Server\n\nHello world.\n"

failures = []


def run(manifest_path, repo_dir=None, extra=()):
    cmd = [sys.executable, str(CHECK_PY), str(manifest_path), *extra]
    if repo_dir is not None:
        cmd += ["--repo-dir", str(repo_dir)]
    return subprocess.run(cmd, capture_output=True, text=True)


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


_case_n = [0]


def write_case(tmp, manifest, readme=GOOD_README, raw=None):
    _case_n[0] += 1
    d = Path(tmp) / f"case{_case_n[0]}"
    d.mkdir(exist_ok=True)
    mf = d / "server.json"
    mf.write_text(raw if raw is not None else json.dumps(manifest), encoding="utf-8")
    if readme is not None:
        (d / "README.md").write_text(readme, encoding="utf-8")
    return mf, d


def main():
    with tempfile.TemporaryDirectory() as tmp:
        # 1. valid manifest + good README -> exit 0 -------------------------
        mf, d = write_case(tmp, VALID_MANIFEST)
        r = run(mf, d)
        check("valid manifest exits 0", r.returncode == 0, f"got {r.returncode}: {r.stdout}{r.stderr}")
        check("valid manifest reports all-passed", "all 10 readiness checks passed" in r.stdout)

        # 2. missing file -> exit 1, RC-001 --------------------------------
        r = run(Path(tmp) / "does-not-exist.json", Path(tmp))
        check("missing file exits 1", r.returncode == 1, f"got {r.returncode}")
        check("missing file fires RC-001", "RC-001" in (r.stdout + r.stderr))

        # 3. invalid JSON -> exit 1, RC-001 --------------------------------
        mf, d = write_case(tmp, None, raw="{not json")
        r = run(mf, d)
        check("invalid JSON exits 1", r.returncode == 1, f"got {r.returncode}")
        check("invalid JSON fires RC-001", "RC-001" in (r.stdout + r.stderr))

        # 4. bad name -> exit 1, RC-002 ------------------------------------
        bad = dict(VALID_MANIFEST, name="not a valid name!!")
        mf, d = write_case(tmp, bad)
        r = run(mf, d)
        check("bad name exits 1", r.returncode == 1, f"got {r.returncode}")
        check("bad name fires RC-002", "RC-002" in r.stdout)

        # 5. bad semver -> exit 1, RC-003 ----------------------------------
        bad = dict(VALID_MANIFEST, version="1.0")
        mf, d = write_case(tmp, bad)
        r = run(mf, d)
        check("bad semver exits 1", r.returncode == 1, f"got {r.returncode}")
        check("bad semver fires RC-003", "RC-003" in r.stdout)

        # 6. missing description -> exit 1, RC-004 ------------------------
        bad = dict(VALID_MANIFEST)
        del bad["description"]
        mf, d = write_case(tmp, bad)
        r = run(mf, d)
        check("missing description exits 1", r.returncode == 1, f"got {r.returncode}")
        check("missing description fires RC-004", "RC-004" in r.stdout)

        # 7. missing repository.url -> exit 1, RC-005 ----------------------
        bad = dict(VALID_MANIFEST, repository={"source": "github"})
        mf, d = write_case(tmp, bad)
        r = run(mf, d)
        check("missing repository.url exits 1", r.returncode == 1, f"got {r.returncode}")
        check("missing repository.url fires RC-005", "RC-005" in r.stdout)

        # 8. missing transport -> exit 1, RC-006 ---------------------------
        bad = dict(VALID_MANIFEST, packages=[{"registryType": "pypi", "identifier": "x"}])
        mf, d = write_case(tmp, bad)
        r = run(mf, d)
        check("missing transport exits 1", r.returncode == 1, f"got {r.returncode}")
        check("missing transport fires RC-006", "RC-006" in r.stdout)

        # 8b. unknown transport type -> exit 1, RC-006 --------------------
        bad = dict(VALID_MANIFEST)
        bad = json.loads(json.dumps(bad))
        bad["packages"][0]["transport"] = {"type": "telepathy"}
        mf, d = write_case(tmp, bad)
        r = run(mf, d)
        check("unknown transport exits 1", r.returncode == 1, f"got {r.returncode}")
        check("unknown transport fires RC-006", "RC-006" in r.stdout)

        # 9. secret-looking value -> exit 1, RC-007 ------------------------
        bad = json.loads(json.dumps(VALID_MANIFEST))
        bad["api_key"] = "sk-abcdefghij1234567890XYZabc"
        mf, d = write_case(tmp, bad)
        r = run(mf, d)
        check("secret value exits 1", r.returncode == 1, f"got {r.returncode}")
        check("secret value fires RC-007", "RC-007" in r.stdout)

        # 10. missing license -> exit 2 (warnings only), RC-008 -----------
        bad = dict(VALID_MANIFEST)
        del bad["license"]
        mf, d = write_case(tmp, bad)
        r = run(mf, d)
        check("missing license exits 2", r.returncode == 2, f"got {r.returncode}")
        check("missing license fires RC-008", "RC-008" in r.stdout)

        # 11. missing README -> exit 2, RC-009 -----------------------------
        mf, d = write_case(tmp, VALID_MANIFEST, readme=None)
        r = run(mf, d)
        check("missing README exits 2", r.returncode == 2, f"got {r.returncode}")
        check("missing README fires RC-009", "RC-009" in r.stdout)

        # 12. README without install/usage -> exit 2, RC-010 ---------------
        mf, d = write_case(tmp, VALID_MANIFEST, readme=BARE_README)
        r = run(mf, d)
        check("bare README exits 2", r.returncode == 2, f"got {r.returncode}")
        check("bare README fires RC-010", "RC-010" in r.stdout)

        # 13. --json output parses and carries the exit code --------------
        mf, d = write_case(tmp, VALID_MANIFEST)
        r = run(mf, d, extra=("--json",))
        try:
            payload = json.loads(r.stdout)
            ok = payload["exit_code"] == 0 and payload["errors"] == [] and payload["warnings"] == []
        except (json.JSONDecodeError, KeyError):
            ok = False
        check("--json output is valid and clean", ok, r.stdout[:200])

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S): {', '.join(failures)}")
        return 1
    print("all tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
