# MCP Readiness Check

Free GitHub Action by **Payload** — *small software that earns its keep.*

Runs 10 basic MCP server readiness checks against your `server.json` on every
pull request. Catches the common manifest mistakes that break registry
publication and confuse consumers — before they land in `main`.

No dependencies. No Docker. Just Python 3 on `ubuntu-latest`.

## Usage

Create `.github/workflows/mcp-readiness.yml` in your MCP server repo:

```yaml
name: MCP readiness
on: [pull_request]

jobs:
  readiness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: Payloadhq/mcp-readiness-check@v1
        with:
          manifest-path: server.json   # path to your manifest (default: server.json)
          fail-on: error              # 'error' (default) or 'warning'
```

- `manifest-path`: where your `server.json` lives, relative to the repo root.
- `fail-on: error` (default): the step fails only on errors; warnings are
  reported but don't block the PR. Use `fail-on: warning` to block on
  warnings too.

## The 10 checks

**Errors** (fail the step):

| Code | Check |
|------|-------|
| RC-001 | `server.json` is present and parses as valid JSON |
| RC-002 | `name` matches the official pattern and the `io.github.<owner>/<server>` registry convention |
| RC-003 | `version` is present and semantic versioning (`x.y.z`) |
| RC-004 | `description` is present and non-empty |
| RC-005 | `repository.url` is present |
| RC-006 | a transport is declared and uses a known type (`stdio`, `streamable-http`, `sse`) |
| RC-007 | no obvious secret values in the manifest (heuristic: `sk-`, `ghp_`/`gho_`/`github_pat_`, `AKIA`, `xox-` style tokens) |

**Warnings** (reported; fail the step only with `fail-on: warning`):

| Code | Check |
|------|-------|
| RC-008 | `license` is declared |
| RC-009 | a README file exists next to the manifest |
| RC-010 | the README mentions install/usage documentation |

Exit codes when run directly: `0` clean, `1` errors found, `2` warnings only.

## Sample output

```
$ python3 check.py server.json
WARN  [RC-008] $: no "license" field declared
0 error(s), 1 warning(s)
```

Machine-readable output with `--json`:

```json
{
  "file": "server.json",
  "errors": [],
  "warnings": [
    {"code": "RC-008", "location": "$", "message": "no \"license\" field declared"}
  ],
  "exit_code": 2
}
```

## What this doesn't do

This Action is a deliberately small safety net: 10 basic checks, written from
scratch. It does not scan your server code, test your tools, check for prompt
injection, audit authentication, or verify hardening.

For the full picture — the **MCP Launch Readiness Audit** ($79, one-time)
runs a 48-rule security and launch-readiness scan with a fix for every finding,
plus hardening templates, a stress-test harness, a readiness verifier, and a
CI workflow:

https://payloadtools.gumroad.com/l/mcp-launch-readiness-audit

## Local use

```bash
python3 check.py path/to/server.json [--repo-dir DIR] [--json]
```

## License

MIT — Copyright 2026 Payload. See [LICENSE](LICENSE).

Support: kylers.partners@gmail.com · https://github.com/Payloadhq
