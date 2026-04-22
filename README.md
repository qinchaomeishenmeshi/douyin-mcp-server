# 抖音下载器 MCP Server

将抖音解析和下载能力封装为一个可直接挂载的 MCP (Model Context Protocol) 服务。

这个仓库已经内置了运行所需的 downloader runtime 子集，不再依赖外部 `douyin-downloader` checkout。别人拿到仓库后，安装依赖即可直接挂载到 Codex、Claude Desktop、Cursor、WorkBuddy 等支持 stdio MCP 的客户端。

## 先看哪份文档

### 给人看的版本

如果你想快速理解它是什么、怎么安装、怎么挂载、遇到问题怎么排查，先看：

[docs/HUMAN_SETUP.md](/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/docs/HUMAN_SETUP.md)

### 给 agent 看的版本

如果你是 agent，或者你想要一份可以直接照抄执行的 runbook，先看：

[docs/AGENT_RUNBOOK.md](/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/docs/AGENT_RUNBOOK.md)

## 一页摘要

### 这个仓库提供什么

| 工具 | 说明 | 同步/异步 |
|------|------|----------|
| `resolve_and_download` | 一键解析链接并下载（自动识别类型） | 混合 |
| `parse_link` | 解析抖音分享链接，获取资源类型和资源 ID | 同步 |
| `get_video_info` | 获取单个作品（视频/图集）详情 | 同步 |
| `get_user_info` | 获取用户主页作品列表 | 同步 |
| `get_user_detail` | 获取用户详细信息（昵称、粉丝等） | 同步 |
| `get_mix_info` | 获取合集作品列表 | 同步 |
| `get_music_info` | 获取音乐（原声）下的作品列表 | 同步 |
| `get_live_info` | 获取直播间信息 | 同步 |
| `download` | 下载单个作品 | 同步 |
| `download_user` | 批量下载用户主页作品 | 异步 |
| `get_task_status` | 查询异步任务进度 | 同步 |
| `set_cookie` | 设置或更新请求 Cookie | 同步 |

### 最短安装路径

```bash
cd douyin-mcp-server
python3.11 -m pip install .
python3.11 -m playwright install chromium
douyin-mcp-server --help
douyin-mcp-smoke --help
```

### 最短 Codex 挂载路径

```bash
codex mcp add douyin-downloader -- douyin-mcp-server
codex mcp list
codex mcp get douyin-downloader
```

### 最短 Claude Desktop 挂载配置

```json
{
  "mcpServers": {
    "douyin-downloader": {
      "command": "douyin-mcp-server"
    }
  }
}
```

## 对人类的重要说明

- 部分接口需要登录态 Cookie。需要时在 MCP 客户端里调用 `set_cookie(...)`。
- `get_video_info` 在详情接口不稳定时会回退到 Playwright，所以建议安装 Chromium。
- 异步任务状态是进程内内存态，不是持久化任务系统。

## 可选联网 smoke test

如果你想在真实挂载前验证 `set_cookie -> parse_link -> get_video_info` 这一条链路，可以用：

```bash
DOUYIN_COOKIE='你的真实 cookie'
douyin-mcp-smoke \
  --share-url 'https://v.douyin.com/你的链接/' \
  --strict
```

如果你还没安装成命令，也可以直接从仓库运行：

```bash
DOUYIN_COOKIE='你的真实 cookie'
python3.11 scripts/smoke_test.py \
  --share-url 'https://v.douyin.com/你的链接/' \
  --strict
```

这个 smoke test 是可选的真实联网验证，不是安装前置步骤。

## 对 agent 的最小执行清单

按下面顺序执行：

```bash
python3.11 -m pip install .
python3.11 -m playwright install chromium
python3.11 -m pytest -q
douyin-mcp-server --help
douyin-mcp-smoke --help
codex mcp add douyin-downloader -- douyin-mcp-server
codex mcp get douyin-downloader
```

## 仓库结构

```text
server.py               FastMCP 服务入口
apiproxy/               已 vendored 的抖音解析/下载运行时子集
utils/logger.py         vendored 运行时日志支持
scripts/legacy/         仅供历史本地批处理使用的旧脚本
docs/                   人类版与 agent 版文档
tests/                  分发、安装和导入验证
```

## 当前验证

```bash
python3.11 -m pytest -q
```
