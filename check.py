#!/usr/bin/env python3
"""
mcp-readiness-check — basic MCP server readiness checks for CI.

Runs a small, safe subset of readiness checks against an MCP server.json
manifest plus the repo's README. Written from scratch for the free
Payload GitHub Action; it is NOT the paid MCP Launch Readiness Audit
(48 rules, hardening templates, remediation guidance).

The 10 checks (RC-001..RC-010):

  Errors:
    RC-001  server.json is present and parses as JSON
    RC-002  "name" matches the official pattern and the
            io.github.<owner>/<server> registry convention
    RC-003  "version" is present and semantic versioning (x.y.z)
    RC-004  "description" is present and non-empty
    RC-005  "repository.url" is present
    RC-006  a transport is declared and uses a known type
            (stdio, streamable-http, sse)
    RC-007  no obvious secret values in the manifest (heuristic:
            sk- / ghp_ / gho_ / github_pat_ / AKIA / xox- style tokens)

  Warnings:
    RC-008  "license" is declared
    RC-009  a README file exists next to the manifest
    RC-010  the README mentions install/usage documentation

Exit codes: 0 = clean, 1 = errors found, 2 = warnings only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

NAME_PATTERN = re.compile(r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$")
GITHUB_NAME_PATTERN = re.compile(r"^io\.github\.([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$")
KNOWN_TRANSPORTS = ("stdio", "streamable-http", "sse")
REMOTE_TRANSPORTS = ("streamable-http", "sse")

# Heuristic secret shapes. Intentionally narrow to avoid false positives:
# a value must look like a real token, not just contain a keyword.
SECRET_PATTERNS = (
    ("sk-", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("ghp_/gho_/github_pat_", re.compile(r"(?:ghp|gho)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9]{20,}")),
    ("AKIA", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("xox-", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
)

README_NAMES = ("README.md", "README", "readme.md", "readme")
INSTALL_HINTS = ("install", "usage", "quickstart", "quick start", "getting started")


class Issue:
    def __init__(self, code: str, severity: str, location: str, message: str):
        self.code = code
        self.severity = severity  # "ERROR" or "WARN"
        self.location = location
        self.message = message

    def __str__(self) -> str:
        return f"{self.severity:5} [{self.code}] {self.location}: {self.message}"


def _iter_strings(value, path="$"):
    """Yield (path, string) for every string value in a JSON document."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _iter_strings(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _iter_strings(v, f"{path}[{i}]")


def _find_transports(data: dict) -> list[tuple[str, dict | str | None]]:
    """Collect (location, transport) declarations from the manifest."""
    found = []
    packages = data.get("packages")
    if isinstance(packages, list):
        for i, pkg in enumerate(packages):
            if isinstance(pkg, dict) and "transport" in pkg:
                found.append((f"packages[{i}].transport", pkg["transport"]))
    if "transport" in data:
        found.append(("transport", data["transport"]))
    return found


def check_manifest(data: dict, repo_dir: Path) -> list[Issue]:
    issues: list[Issue] = []

    if not isinstance(data, dict):
        return [Issue("RC-001", "ERROR", "$",
                      "manifest root must be a JSON object")]

    # RC-002: name format -------------------------------------------------
    name = data.get("name")
    if not isinstance(name, str) or not name:
        issues.append(Issue("RC-002", "ERROR", "name",
                            'missing required field "name"'))
    elif not NAME_PATTERN.match(name):
        issues.append(Issue(
            "RC-002", "ERROR", "name",
            f"{name!r} does not match the official name pattern "
            r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$"))
    elif not GITHUB_NAME_PATTERN.match(name):
        issues.append(Issue(
            "RC-002", "ERROR", "name",
            f"{name!r} does not follow the io.github.<owner>/<server> "
            "registry convention"))

    # RC-003: semver ------------------------------------------------------
    version = data.get("version")
    if not isinstance(version, str) or not version:
        issues.append(Issue("RC-003", "ERROR", "version",
                            'missing required field "version"'))
    elif not SEMVER_PATTERN.match(version):
        issues.append(Issue("RC-003", "ERROR", "version",
                            f"{version!r} is not semantic versioning (x.y.z)"))

    # RC-004: description -------------------------------------------------
    if not isinstance(data.get("description"), str) or not data.get("description", "").strip():
        issues.append(Issue("RC-004", "ERROR", "description",
                            'missing required field "description"'))

    # RC-005: repository.url ----------------------------------------------
    repo = data.get("repository")
    if not isinstance(repo, dict) or not isinstance(repo.get("url"), str) \
            or not repo.get("url", "").strip():
        issues.append(Issue("RC-005", "ERROR", "repository.url",
                            'missing required field "repository.url"'))

    # RC-006: transport declared and valid ---------------------------------
    transports = _find_transports(data)
    if not transports:
        issues.append(Issue("RC-006", "ERROR", "transport",
                            "no transport declared (expected "
                            "packages[].transport.type or top-level "
                            '"transport")'))
    else:
        for loc, transport in transports:
            ttype = transport.get("type") if isinstance(transport, dict) \
                else transport
            if ttype not in KNOWN_TRANSPORTS:
                issues.append(Issue(
                    "RC-006", "ERROR", loc,
                    f"unknown transport type {ttype!r} "
                    f"(known: {', '.join(KNOWN_TRANSPORTS)})"))
            elif ttype in REMOTE_TRANSPORTS:
                url = transport.get("url") if isinstance(transport, dict) else None
                if not url:
                    issues.append(Issue(
                        "RC-006", "WARN", loc,
                        f'remote transport "{ttype}" declares no "url"'))

    # RC-007: no obvious secrets ------------------------------------------
    for path, value in _iter_strings(data):
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(value):
                issues.append(Issue(
                    "RC-007", "ERROR", path,
                    f"value looks like a leaked {label} secret; "
                    "remove it before committing"))
                break  # one finding per value is enough

    # RC-008: license ------------------------------------------------------
    if not isinstance(data.get("license"), str) or not data.get("license", "").strip():
        issues.append(Issue("RC-008", "WARN", "$",
                            'no "license" field declared'))

    # RC-009 / RC-010: README ----------------------------------------------
    readme = next((repo_dir / n for n in README_NAMES
                   if (repo_dir / n).is_file()), None)
    if readme is None:
        issues.append(Issue("RC-009", "WARN", "$",
                            "no README file found next to the manifest"))
    else:
        try:
            text = readme.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            text = ""
        if not any(hint in text for hint in INSTALL_HINTS):
            issues.append(Issue(
                "RC-010", "WARN", readme.name,
                "README does not mention install/usage documentation"))

    return issues


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run basic MCP server readiness checks.")
    ap.add_argument("manifest", help="path to server.json")
    ap.add_argument("--repo-dir",
                    help="directory holding the README (default: the "
                         "manifest's directory)")
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON instead of text")
    args = ap.parse_args(argv)

    manifest_path = Path(args.manifest)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR [RC-001] $: file not found: {args.manifest}",
              file=sys.stderr)
        print("1 error, 0 warnings", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR [RC-001] $: invalid JSON: {exc}", file=sys.stderr)
        print("1 error, 0 warnings", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR [RC-001] $: cannot read {args.manifest}: {exc}",
              file=sys.stderr)
        return 1

    repo_dir = Path(args.repo_dir) if args.repo_dir else manifest_path.parent
    issues = check_manifest(data, repo_dir)
    errors = [i for i in issues if i.severity == "ERROR"]
    warns = [i for i in issues if i.severity == "WARN"]

    if args.json:
        print(json.dumps({
            "file": args.manifest,
            "errors": [{"code": i.code, "location": i.location,
                        "message": i.message} for i in errors],
            "warnings": [{"code": i.code, "location": i.location,
                          "message": i.message} for i in warns],
            "exit_code": 1 if errors else (2 if warns else 0),
        }, indent=2))
    else:
        for issue in issues:
            print(issue)
        if issues:
            print(f"{len(errors)} error(s), {len(warns)} warning(s)")
        else:
            print("all 10 readiness checks passed")

    if errors:
        return 1
    if warns:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
