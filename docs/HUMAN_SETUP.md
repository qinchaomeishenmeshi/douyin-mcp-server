# 人类使用说明

## 这份文档适合谁

这份文档适合想自己安装、挂载和使用这个 MCP 的人。

如果你只想快速看总览，请先看 [README.md](/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/README.md)。  
如果你要把步骤交给 agent 执行，请看 [docs/AGENT_RUNBOOK.md](/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/docs/AGENT_RUNBOOK.md)。

## 这是什么

这是一个自包含的抖音 MCP 服务仓库，用来提供解析、查询和下载能力。

和早期依赖外部 `douyin-downloader` checkout 的做法不同，这个仓库已经把运行时需要的核心子集直接整合进来。正常情况下，你不需要再准备额外的 downloader 仓库。

## 你需要准备什么

- Python `3.11`
- 可以安装 Python 依赖的网络环境
- 一个支持 stdio MCP 的客户端，例如 Codex 或 Claude Desktop
- 如果你要访问受限接口，还需要一份有效的抖音登录态 Cookie

## 推荐安装方式

推荐优先把它安装成命令。这样最接近别人实际挂载这个仓库的方式，也最容易复用。

```bash
cd douyin-mcp-server
python3.11 -m pip install .
python3.11 -m playwright install chromium
```

安装完成后，先确认两个命令都能正常输出帮助信息：

```bash
douyin-mcp-server --help
douyin-mcp-smoke --help
```

这里的 `chromium` 很重要。`get_video_info` 在详情接口不稳定时，会回退到 Playwright 浏览器路径；如果不安装 Chromium，部分真实查询会失败。

## 如果你不想安装成命令

你也可以直接从仓库运行：

```bash
cd douyin-mcp-server
python3.11 -m pip install -r requirements.txt
python3.11 -m playwright install chromium
python3.11 server.py --help
```

这种方式适合本地临时调试，但如果你要给别人复用，还是更推荐安装成命令。

## 挂载到 Codex

### 如果已经安装成命令

```bash
codex mcp add douyin-downloader -- douyin-mcp-server
```

### 如果直接从仓库运行

```bash
codex mcp add douyin-downloader -- python3.11 -u /ABSOLUTE/PATH/TO/douyin-mcp-server/server.py
```

挂载后可以用下面两条命令确认结果：

```bash
codex mcp list
codex mcp get douyin-downloader
```

## 挂载到 Claude Desktop

### 如果已经安装成命令

```json
{
  "mcpServers": {
    "douyin-downloader": {
      "command": "douyin-mcp-server"
    }
  }
}
```

### 如果直接从仓库运行

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

## 第一次使用建议

部分接口需要登录态 Cookie。最常见的做法是在 MCP 客户端里先调用：

```text
set_cookie("name1=value1; name2=value2; ...")
```

然后建议优先测试下面三类能力：

- `parse_link`
- `get_video_info`
- `resolve_and_download`

这样最容易快速判断当前安装、Cookie 和依赖是否都正常。

## 安装后的快速检查

如果你想在正式挂载前先做一轮本地检查，可以运行：

```bash
python3.11 -m pytest -q
python3.11 server.py --help
```

如果你已经安装成命令，也建议补跑：

```bash
douyin-mcp-server --help
douyin-mcp-smoke --help
```

## 可选的真实联网 smoke test

如果你想在正式交给别人使用前，验证真实的 `set_cookie -> parse_link -> get_video_info` 链路，可以运行：

```bash
DOUYIN_COOKIE='你的真实 cookie'
douyin-mcp-smoke \
  --share-url 'https://v.douyin.com/你的分享链接/' \
  --strict
```

如果你还没有安装成命令，也可以直接从仓库运行：

```bash
DOUYIN_COOKIE='你的真实 cookie'
python3.11 scripts/smoke_test.py \
  --share-url 'https://v.douyin.com/你的分享链接/' \
  --strict
```

这个 smoke test 是可选的，不是安装前置条件。它依赖真实网络、真实分享链接，以及通常需要有效 Cookie。

## 已知限制

- 异步任务状态只保存在当前 MCP 进程内存里。进程退出后，任务状态不会保留。
- 抖音接口可能限流，也可能出现阶段性不稳定。
- Playwright 是详情查询的回退依赖，不建议省略 Chromium 安装。

## 常见问题

### `ModuleNotFoundError`

通常说明依赖没有安装完整。优先重新执行：

```bash
python3.11 -m pip install .
```

### `get_video_info` 结果为空，或者表现不稳定

先确认 Chromium 是否已经安装：

```bash
python3.11 -m playwright install chromium
```

如果 Chromium 已经安装，再检查 Cookie 是否过期，或者是否遇到了抖音接口波动。

### 受限数据拿不到

通常是 Cookie 无效、过期，或者当前账号权限不足。请重新在客户端里调用 `set_cookie(...)`。

### 异步任务状态丢失

这是当前设计的预期行为，不是单独的 bug。任务状态只存在于当前 MCP 进程内，进程结束后就会丢失。
