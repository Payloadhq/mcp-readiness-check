# MCP Readiness Check

**Free GitHub Action: 10 MCP server readiness checks on every PR. By Payload.**

Runs against your `server.json` on every pull request and catches the common
manifest mistakes that break registry publication and confuse consumers,
before they land in `main`.

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
          fail-on: error               # 'error' (default) or 'warning'
```

- `manifest-path`: where your `server.json` lives, relative to the repo root.
- `fail-on: error` (default): the step fails only on errors; warnings are
  reported but don't block the PR. Use `fail-on: warning` to block on
  warnings too.

## The 10 checks

**Errors** (fail the step): RC-001 valid JSON · RC-002 `name` matches the
`io.github.<owner>/<server>` registry convention · RC-003 semver `version` ·
RC-004 non-empty `description` · RC-005 `repository.url` present · RC-006
known transport (`stdio`, `streamable-http`, `sse`) · RC-007 no obvious
secret values in the manifest.

**Warnings** (fail the step only with `fail-on: warning`): RC-008 `license`
declared · RC-009 README exists next to the manifest · RC-010 README covers
install/usage.

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

## Local use

```bash
python3 check.py path/to/server.json [--repo-dir DIR] [--json]
```

## Beyond this check

- **Full audit:** Payload's MCP Launch Readiness Audit
  ([payloadtools.gumroad.com/l/mcp-launch-readiness-audit](https://payloadtools.gumroad.com/l/mcp-launch-readiness-audit),
  $79 one-time) runs a 48-rule security and launch-readiness scan with a fix
  for every finding, plus hardening templates, a stress-test harness, a
  readiness verifier, and a CI workflow.
- **When your MCP server goes live:** Veyline by Payload is the production
  layer for x402 + MCP: autonomous economic control for machine commerce.

Built by [Payload](https://payloadhq.github.io/). Support: kylers.partners@gmail.com.

## License

MIT. Copyright 2026 Payload. See [LICENSE](LICENSE).

---

**More from Payload** · [payloadhq.github.io](https://payloadhq.github.io/) · [all Payload repos](https://github.com/Payloadhq)

Related: [mcp-manifest-validator](https://github.com/Payloadhq/mcp-manifest-validator) · [payload-sample-mcp-server](https://github.com/Payloadhq/payload-sample-mcp-server)
