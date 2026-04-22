# Agent 执行手册

## 目标

把这个仓库安装、验证并挂载成一个可直接使用的抖音 MCP 服务，而且整个过程不依赖任何外部 `douyin-downloader` checkout。

## 适用场景

这份 runbook 适合 agent 直接照着执行，也适合人类把步骤交给 agent 代跑。

如果你只需要仓库总览，请先看 [README.md](../README.md)。  
如果你要给人类用户提供更友好的操作说明，请看 [docs/HUMAN_SETUP.md](HUMAN_SETUP.md)。

## 前置假设

- 当前工作目录是仓库根目录
- Python `3.11` 可用
- 目标客户端支持 stdio MCP server
- 如果需要访问受限接口，人类可以提供有效的抖音 Cookie

## 推荐执行路径

按下面顺序执行：

```bash
python3.11 -m pip install .
python3.11 -m playwright install chromium
python3.11 -m pytest -q
douyin-mcp-server --help
douyin-mcp-smoke --help
```

期望结果：

- `pytest` 通过
- `douyin-mcp-server --help` 退出码为 `0`
- `douyin-mcp-smoke --help` 退出码为 `0`

不要跳过 `playwright install chromium`。真实联调已经验证过，`get_video_info` 在详情接口返回空响应时，会回退到 Playwright 浏览器路径；如果没有 Chromium，链路会在回退阶段失败。

## Codex 挂载

优先使用安装后命令路径：

```bash
codex mcp add douyin-downloader -- douyin-mcp-server
```

校验命令：

```bash
codex mcp list
codex mcp get douyin-downloader
```

## Claude Desktop 挂载

如果已经安装成命令，使用：

```json
{
  "mcpServers": {
    "douyin-downloader": {
      "command": "douyin-mcp-server"
    }
  }
}
```

如果不走安装路径，而是直接从仓库运行，使用：

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

## 仓库直跑回退路径

如果安装成命令失败，先不要假设仓库本身不可用。先验证仓库直跑路径：

```bash
python3.11 -m pip install -r requirements.txt
python3.11 -m playwright install chromium
python3.11 server.py --help
```

然后再用绝对路径挂载：

```bash
codex mcp add douyin-downloader -- python3.11 -u /ABSOLUTE/PATH/TO/douyin-mcp-server/server.py
```

## 最小健康检查

### 仓库模式检查

```bash
python3.11 server.py --help
python3.11 - <<'PY'
import server
print(callable(server.main))
print(server.get_task_status("missing"))
PY
```

期望结果：

- 帮助文本正常输出
- `callable(server.main)` 为 `True`
- 不存在的任务返回错误字典，而不是导入失败

### 分发模式检查

```bash
python3.11 -m pytest -q tests/test_distribution.py
```

这个测试覆盖的点包括：

- 仓库可以脱离外部 downloader checkout 单独分发
- `pyproject.toml` 存在
- `server.main()` 存在
- 安装后的 console script 可以正常输出 `--help`
- 仓库自带的 smoke script 可以正常输出 `--help`

## Cookie 处理约束

如果需要访问受限接口，引导用户在 MCP 客户端里调用：

```text
set_cookie("name1=value1; name2=value2; ...")
```

不要把真实 Cookie 写入仓库文件、示例配置或提交记录。

## 可选的真实联网 smoke test

只有在用户明确提供真实 share URL 和真实 Cookie，且需要做在线验证时，才运行下面的命令。

已安装命令时：

```bash
DOUYIN_COOKIE='real cookie'
douyin-mcp-smoke \
  --share-url 'https://v.douyin.com/real-share-url/' \
  --strict
```

仓库模式时：

```bash
DOUYIN_COOKIE='real cookie'
python3.11 scripts/smoke_test.py \
  --share-url 'https://v.douyin.com/real-share-url/' \
  --strict
```

期望行为：

- 如果提供了 Cookie，先输出 `set_cookie`
- `parse_link` 返回 `key_type`
- 如果 `key_type == "aweme"`，继续调用 `get_video_info`
- 开启 `--strict` 后，只要 MCP 返回错误 payload，就应该以非零退出码结束

## 运行限制

- 异步任务状态只存在于当前进程内存中，不会持久化
- 批量下载适合本地工作站会话，不适合作为持久任务队列
- Playwright 不是装饰性依赖，而是详情接口异常时的回退依赖

## 启动失败时的排查顺序

按下面顺序排查，不要跳步：

```bash
python3.11 -m pip install .
python3.11 -m playwright install chromium
python3.11 -m pytest -q tests/test_distribution.py
douyin-mcp-server --help
```

如果安装后的命令仍然无法启动，再切换到仓库模式：

```bash
python3.11 -u /ABSOLUTE/PATH/TO/douyin-mcp-server/server.py --help
```

如果真实联网 smoke test 失败，优先按下面顺序判断原因：

1. Chromium 是否已安装
2. Cookie 是否有效
3. 抖音详情接口是否出现空响应
4. 是否已经触发 Playwright 回退路径

## 交付时建议回报什么

如果 agent 需要向人类回报执行结果，建议至少包含：

- 安装是否成功
- `pytest` 是否通过
- `douyin-mcp-server --help` 是否正常
- 是否已经完成 MCP 挂载
- 如果做了真实联调，`set_cookie -> parse_link -> get_video_info` 是否跑通
