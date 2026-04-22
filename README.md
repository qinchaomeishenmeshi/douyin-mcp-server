# 抖音下载器 MCP Server

把抖音解析与下载能力封装成一个可直接挂载的 MCP 服务。

这个仓库已经把运行所需的 `douyin-downloader` runtime 子集直接整合进来，不再依赖额外的 downloader checkout。拿到仓库后，只要安装依赖并注册一个 stdio MCP server，就可以直接挂载到 Codex、Claude Desktop、Cursor、WorkBuddy 等客户端。

## 这份 README 适合谁

- 想快速判断这个仓库能不能直接用
- 想知道最短安装路径、最短挂载路径和最短验证路径
- 想先看总览，再决定是否继续读详细文档

如果你需要更细的步骤，请继续看：

- 人类使用说明：[docs/HUMAN_SETUP.md](/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/docs/HUMAN_SETUP.md)
- Agent 执行手册：[docs/AGENT_RUNBOOK.md](/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/docs/AGENT_RUNBOOK.md)

## 先说结论

- 这是一个“别人拿走就能挂载”的自包含 MCP 仓库
- 安装时建议同时安装 Playwright Chromium，因为 `get_video_info` 在详情接口不稳定时会回退到 Playwright
- 部分受限接口需要登录态 Cookie，通常通过 `set_cookie(...)` 注入
- 异步任务状态是进程内内存态，不是持久化任务队列

## 推荐使用路径

推荐优先走“安装成命令”的路径。这样最接近第三方实际挂载场景，也最容易验证。

### 1. 安装

```bash
cd douyin-mcp-server
python3.11 -m pip install .
python3.11 -m playwright install chromium
```

### 2. 本地自检

```bash
python3.11 -m pytest -q
douyin-mcp-server --help
douyin-mcp-smoke --help
```

### 3. 挂载到 Codex

```bash
codex mcp add douyin-downloader -- douyin-mcp-server
codex mcp list
codex mcp get douyin-downloader
```

### 4. 挂载到 Claude Desktop

```json
{
  "mcpServers": {
    "douyin-downloader": {
      "command": "douyin-mcp-server"
    }
  }
}
```

## 如果你不想安装成命令

也可以直接从仓库运行：

```bash
cd douyin-mcp-server
python3.11 -m pip install -r requirements.txt
python3.11 -m playwright install chromium
python3.11 server.py --help
```

Codex 挂载示例：

```bash
codex mcp add douyin-downloader -- python3.11 -u /ABSOLUTE/PATH/TO/douyin-mcp-server/server.py
```

Claude Desktop 挂载示例：

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

## 这个 MCP 提供什么

| 工具 | 说明 | 类型 |
|------|------|------|
| `resolve_and_download` | 一键解析链接并下载，自动识别资源类型 | 混合 |
| `parse_link` | 解析抖音分享链接，得到资源类型和资源 ID | 同步 |
| `get_video_info` | 获取单个作品详情，支持视频和图集 | 同步 |
| `get_user_info` | 获取用户主页作品列表 | 同步 |
| `get_user_detail` | 获取用户详情信息 | 同步 |
| `get_mix_info` | 获取合集作品列表 | 同步 |
| `get_music_info` | 获取音乐下的作品列表 | 同步 |
| `get_live_info` | 获取直播间信息 | 同步 |
| `download` | 下载单个作品 | 同步 |
| `download_user` | 批量下载用户主页作品 | 异步 |
| `get_task_status` | 查询异步任务进度 | 同步 |
| `set_cookie` | 设置或更新请求 Cookie | 同步 |

## 第一次使用建议

如果你需要访问受限接口，先在 MCP 客户端里调用：

```text
set_cookie("name1=value1; name2=value2; ...")
```

然后优先尝试下面三类能力：

- `parse_link`
- `get_video_info`
- `resolve_and_download`

这样最容易快速判断当前环境、Cookie 和依赖是否正常。

## 可选的真实联网 smoke test

如果你想在正式挂载前，先验证 `set_cookie -> parse_link -> get_video_info` 这一条真实链路，可以运行：

```bash
DOUYIN_COOKIE='你的真实 cookie'
douyin-mcp-smoke \
  --share-url 'https://v.douyin.com/你的链接/' \
  --strict
```

如果你还没有安装成命令，也可以直接从仓库运行：

```bash
DOUYIN_COOKIE='你的真实 cookie'
python3.11 scripts/smoke_test.py \
  --share-url 'https://v.douyin.com/你的链接/' \
  --strict
```

这个 smoke test 不是安装前置步骤，而是一种可选的真实联网验证方式。

## 已验证内容

当前仓库已经验证过以下路径：

- `python3.11 -m pytest -q`
- `python3.11 server.py --help`
- `python3.11 smoke_test.py --help`
- `python3.11 scripts/smoke_test.py --help`
- `pip install -e .` 后执行 `douyin-mcp-server --help`
- `pip install -e .` 后执行 `douyin-mcp-smoke --help`
- 使用真实 Cookie 与真实 share URL 跑通 `set_cookie -> parse_link -> get_video_info`

真实联调里还确认了一点：当详情接口返回空响应时，`get_video_info` 会回退到 Playwright 浏览器路径，因此安装 Chromium 很重要。

## 常见问题

### 1. `ModuleNotFoundError`

通常是因为依赖没有装完整。优先重新执行：

```bash
python3.11 -m pip install .
```

### 2. `get_video_info` 结果为空，或者表现不稳定

先确认 Chromium 已安装：

```bash
python3.11 -m playwright install chromium
```

如果仍然异常，再检查 Cookie 是否有效。

### 3. 受限数据拿不到

通常是登录态不足，或者 Cookie 已过期。请在 MCP 客户端里重新调用 `set_cookie(...)`。

### 4. 异步任务查不到历史状态

这是预期行为。当前任务状态只保存在 MCP 进程内存里，进程退出后状态会丢失。

## 仓库结构

```text
server.py               FastMCP 服务入口
apiproxy/               已 vendored 的抖音解析与下载 runtime 子集
utils/logger.py         vendored runtime 的日志支持
scripts/legacy/         历史本地批处理脚本，不属于分发主入口
docs/                   人类版与 agent 版文档
tests/                  分发、安装与导入验证
```

## 适合继续阅读哪份文档

- 你想把它挂到自己的客户端里，优先看 [docs/HUMAN_SETUP.md](/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/docs/HUMAN_SETUP.md)
- 你是 agent，或者要把执行步骤交给 agent，优先看 [docs/AGENT_RUNBOOK.md](/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/docs/AGENT_RUNBOOK.md)
