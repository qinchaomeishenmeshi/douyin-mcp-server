# Human Setup Guide

## What this is

This repository is a self-contained MCP server for Douyin parsing and downloading.

You do not need a separate `douyin-downloader` checkout anymore. If you can install Python packages and register a stdio MCP server in your client, you can use this repository directly.

## What you need

- Python `3.11`
- Network access for Python package installation
- An MCP client such as Codex or Claude Desktop
- A valid Douyin cookie for restricted endpoints

## Install

### Option 1: Install as a reusable command

```bash
cd douyin-mcp-server
python3.11 -m pip install .
python3.11 -m playwright install chromium
```

After installation, you should have:

```bash
douyin-mcp-server --help
douyin-mcp-smoke --help
```

### Option 2: Run directly from the repository

```bash
cd douyin-mcp-server
python3.11 -m pip install -r requirements.txt
python3.11 -m playwright install chromium
python3.11 server.py --help
```

## Mount in Codex

### If installed as a command

```bash
codex mcp add douyin-downloader -- douyin-mcp-server
```

### If running from the repository

```bash
codex mcp add douyin-downloader -- python3.11 -u /ABSOLUTE/PATH/TO/douyin-mcp-server/server.py
```

Check the result:

```bash
codex mcp list
codex mcp get douyin-downloader
```

## Mount in Claude Desktop

### If installed as a command

```json
{
  "mcpServers": {
    "douyin-downloader": {
      "command": "douyin-mcp-server"
    }
  }
}
```

### If running from the repository

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

## First use

Some endpoints need a logged-in Douyin cookie. In your MCP client, call:

```text
set_cookie("name1=value1; name2=value2; ...")
```

Then try one of these:

- `parse_link`
- `get_video_info`
- `resolve_and_download`

## Quick checks

Use these if you want to confirm the install is healthy before mounting:

```bash
python3.11 -m pytest -q
python3.11 server.py --help
```

If installed as a package:

```bash
douyin-mcp-server --help
douyin-mcp-smoke --help
```

## Optional real-network smoke test

Use this only if you want to verify a real Douyin request path before mounting or handing the repo to someone else.

```bash
DOUYIN_COOKIE='your real cookie'
douyin-mcp-smoke \
  --share-url 'https://v.douyin.com/your-share-url/' \
  --strict
```

If you are running from the repository without package installation:

```bash
DOUYIN_COOKIE='your real cookie'
python3.11 scripts/smoke_test.py \
  --share-url 'https://v.douyin.com/your-share-url/' \
  --strict
```

What it does:

- applies the cookie with `set_cookie`
- parses the share URL with `parse_link`
- if the result is a single aweme, calls `get_video_info`

This is optional because it depends on real network access, a real share URL, and often a valid cookie.

## Important limits

- Async task status is in-memory only. If the MCP process exits, task state is lost.
- Douyin may rate-limit or block frequent requests.
- Playwright is used as a fallback path for some detail lookups, so Chromium should be installed.

## Common problems

### `ModuleNotFoundError`

You probably skipped dependency installation. Re-run:

```bash
python3.11 -m pip install .
```

### `get_video_info` returns empty or unstable results

Install Playwright Chromium:

```bash
python3.11 -m playwright install chromium
```

### Restricted data is missing

Set a valid cookie with `set_cookie(...)`.
