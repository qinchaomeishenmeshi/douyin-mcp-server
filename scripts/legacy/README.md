# Legacy Local Scripts

这些脚本是仓库早期为了本机批量下载、ASR、去重、汇总而保留下来的本地辅助脚本。

它们不是分发给第三方使用的 MCP 入口，也不是安装后需要挂载的命令。

如果你只是想：

- 安装这个 MCP
- 挂载到 Codex / Claude Desktop
- 做分发级或联网 smoke 验证

请使用仓库根目录里的：

- `server.py`
- `smoke_test.py`
- `scripts/smoke_test.py`

这些 `legacy` 脚本保留下来只是为了兼容历史的本地批处理流程。
