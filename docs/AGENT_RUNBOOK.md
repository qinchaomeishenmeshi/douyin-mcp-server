# Agent Runbook

## Goal

Install, verify, and mount this Douyin MCP server in a way that does not rely on any external `douyin-downloader` checkout.

## Assumptions

- Working directory is the repository root.
- Python `3.11` is available.
- The target MCP client supports stdio servers.
- If restricted endpoints are needed, the human can provide a valid Douyin cookie.

## Fast path

Run these commands in order:

```bash
python3.11 -m pip install .
python3.11 -m playwright install chromium
python3.11 -m pytest -q
douyin-mcp-server --help
douyin-mcp-smoke --help
```

Expected results:

- `pytest` passes
- `douyin-mcp-server --help` exits with code `0`

## Codex mount

Preferred command:

```bash
codex mcp add douyin-downloader -- douyin-mcp-server
```

Verify:

```bash
codex mcp list
codex mcp get douyin-downloader
```

## Claude Desktop mount

Use this config when the package command is available:

```json
{
  "mcpServers": {
    "douyin-downloader": {
      "command": "douyin-mcp-server"
    }
  }
}
```

Fallback config if package installation is not desired:

```json
{
  "mcpServers": {
    "douyin-downloader": {
      "command": "python3.11",
      "args": ["/ABSOLUTE/PATH/TO/douyin-mcp-server/server.py"]
    }
  }
}
```

## Minimal health checks

### Repository mode

```bash
python3.11 server.py --help
python3.11 - <<'PY'
import server
print(callable(server.main))
print(server.get_task_status("missing"))
PY
```

Expected:

- help text prints successfully
- `callable(server.main)` is `True`
- missing task returns an error dict, not an import failure

### Distribution mode

Use this to validate third-party portability:

```bash
python3.11 -m pytest -q tests/test_distribution.py
```

This verifies:

- the repo can be copied without an external downloader checkout
- `pyproject.toml` is present
- `server.main()` exists
- the installed console script starts and serves `--help`
- the repo-distributed smoke script starts and serves `--help`

## Cookie workflow

If the user needs restricted endpoints, tell them to call:

```text
set_cookie("name1=value1; name2=value2; ...")
```

Do not write real cookies into repository files.

## Optional real-network smoke test

Run this only when a human has provided a real share URL and a real cookie, and when live network verification is useful.

Installed-command mode:

```bash
DOUYIN_COOKIE='real cookie'
douyin-mcp-smoke \
  --share-url 'https://v.douyin.com/real-share-url/' \
  --strict
```

Repository mode:

```bash
DOUYIN_COOKIE='real cookie'
python3.11 scripts/smoke_test.py \
  --share-url 'https://v.douyin.com/real-share-url/' \
  --strict
```

Expected behavior:

- `set_cookie` output prints first if a cookie is supplied
- `parse_link` returns a `key_type`
- if `key_type == "aweme"`, `get_video_info` runs next
- `--strict` makes MCP error payloads fail the smoke command with a non-zero exit code

## Operational limits

- Async task state is process-local and non-persistent.
- Batch jobs are suitable for a local workstation session, not as a durable job queue.
- Playwright is a fallback dependency for unstable detail endpoints.

## If startup fails

Run these checks in order:

```bash
python3.11 -m pip install .
python3.11 -m playwright install chromium
python3.11 -m pytest -q tests/test_distribution.py
douyin-mcp-server --help
```

If package-mode startup still fails, use repository mode:

```bash
python3.11 -u /ABSOLUTE/PATH/TO/douyin-mcp-server/server.py --help
```
