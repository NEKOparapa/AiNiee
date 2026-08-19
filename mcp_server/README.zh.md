# ainiee-mcp

[English](README.md) | 中文

一个**通用**的 [MCP](https://modelcontextprotocol.io) 服务器，让 **Claude Code** 和 **Codex**
直接驱动 [AiNiee](https://github.com/NEKOparapa/AiNiee)：启动 / 停止 / 监控翻译与润色任务，运行
分析 / 术语表翻译 / 接口测试，管理 `config.json`（接口、术语表、提示词、语言、项目类型……），并能
**检查与修正译文——全程无需关闭 AiNiee**。

它适用于 AiNiee 支持的**任意文本 / 项目**，本身不含任何项目特定的修正逻辑。

这是 **Phase A**：服务器通过 AiNiee 的 HTTP 服务与*正在运行*的 AiNiee 通信，并直接编辑
`config.json`。后端被封装在 `AiNieeBackend` 抽象层之后，因此未来的无界面进程内后端（Phase B）
只需新增一个文件即可接入。

> 下文路径写作 `<AINIEE>/mcp_server`，其中 `<AINIEE>` 是你克隆 AiNiee 的位置。请替换为你自己的
> 绝对路径（MCP 客户端配置需要绝对路径）。

---

## 1. 启用 AiNiee 的 HTTP 服务（一次性）

在 AiNiee 中：**设置 → 启用 HTTP 监听服务**，设置地址（默认 `127.0.0.1:3388`），然后
**重启 AiNiee**。启动时日志会列出可用的接口。

## 2. 安装服务器

```bash
cd <AINIEE>/mcp_server          # 即包含本 README 的目录
python3 -m venv .venv
./.venv/bin/pip install -e .
```

（运行时仅依赖 `mcp` 和 `httpx`；它从不 import AiNiee，因此保持轻量，且独立于 AiNiee 的
Python 环境。）

## 3. 注册到你的客户端（stdio）

**Claude Code** —— `claude mcp add`：
```bash
claude mcp add ainiee \
  --env AINIEE_HTTP_BASE_URL=http://127.0.0.1:3388 \
  -- <AINIEE>/mcp_server/.venv/bin/python -m ainiee_mcp.server
```
或使用项目级 `.mcp.json`：
```json
{
  "mcpServers": {
    "ainiee": {
      "command": "<AINIEE>/mcp_server/.venv/bin/python",
      "args": ["-m", "ainiee_mcp.server"],
      "env": { "AINIEE_HTTP_BASE_URL": "http://127.0.0.1:3388", "AINIEE_MCP_BACKEND": "http" }
    }
  }
}
```

**Codex** —— `~/.codex/config.toml`：
```toml
[mcp_servers.ainiee]
command = "<AINIEE>/mcp_server/.venv/bin/python"
args = ["-m", "ainiee_mcp.server"]
env = { AINIEE_HTTP_BASE_URL = "http://127.0.0.1:3388", AINIEE_MCP_BACKEND = "http" }
```

### 环境变量
| 变量 | 默认值 | 含义 |
|---|---|---|
| `AINIEE_HTTP_BASE_URL` | `http://127.0.0.1:3388` | AiNiee 的 HTTP 服务监听地址（需与 `http_listen_address` 一致） |
| `AINIEE_HTTP_TIMEOUT` | `30` | 单次请求超时（秒） |
| `AINIEE_MCP_BACKEND` | `http` | 后端类型（Phase A：`http`） |
| `AINIEE_CONFIG` | — | config.json 的直接路径（否则自动解析） |
| `AINIEE_USER_DATA_DIR` / `AINIEE_REPO` | — | 覆盖 config.json 的解析方式（与 AiNiee 的 `FilePathConfig` 一致） |

在 macOS 上，config.json 自动解析为 `~/Library/Application Support/AiNiee/config.json`。

---

## 工具

**翻译控制** —— `ainiee_status`、`ainiee_translate`、`ainiee_polish`、`ainiee_stop`、
`ainiee_load_project`

**扩展任务**（开始 → 轮询 `*_result`）—— `ainiee_analysis_start` / `ainiee_analysis_result`、
`ainiee_glossary_translate` / `ainiee_glossary_result`、`ainiee_api_test` / `ainiee_api_test_result`、
`ainiee_export`、`ainiee_save_cache`、`ainiee_get_analysis`（直接从**已加载项目**的缓存读取此前
提取出的角色 / 术语 / 禁翻表——无需重跑；可选 `kind` 只返回其中一类）

**配置与资源**（编辑 `config.json`；AiNiee 运行时也可安全操作）—— `ainiee_get_config`
（密钥已打码）、`ainiee_list_platforms`、`ainiee_set_platform`、`ainiee_set_active_api`、
`ainiee_set_languages`、`ainiee_set_io_paths`、`ainiee_set_project_type`、`ainiee_set_glossary`、
`ainiee_set_exclusions`、`ainiee_set_pre_post_replacements`、`ainiee_set_characters`、
`ainiee_set_world_style`

**通用译文修正**（操作内存中的实时缓存；无需关闭 AiNiee）—— `ainiee_cache_search`、
`ainiee_cache_stats`、`ainiee_cache_update`、`ainiee_cache_replace`

`ainiee_cache_replace` 接收通用规则 `{find, replace, regex?, scope?, source_requires?,
skip_if_followed_by?}`，并默认 `dry_run=True`（先预览，再应用）。`source_requires` 仅在某条译文的
**原文**匹配指定模式时才执行替换——这是一个安全、通用的守卫，不含任何内置的领域规则。

### 并发
- **配置编辑**在 AiNiee 运行时是安全的（原子写入；AiNiee 在任务开始时重新读取）。
- **缓存编辑**（`cache_update` / `cache_replace`）要求 AiNiee **正在运行、已加载项目、且未在翻译中**
  （IDLE / STOPPED）。它们修改的是 AiNiee 自己的内存缓存并保存——因此**无需关闭 AiNiee**，也不会有
  覆盖风险。（GUI 的编辑视图可能需要重新加载才能显示更改；保存的缓存和任何导出都会反映更改。）

---

## 开发

```bash
./.venv/bin/python -m pytest            # MCP 服务器单元测试（在 mcp_server/ 下运行）
# AiNiee 侧 handler 测试 + 跨进程 E2E（需要 AiNiee 的 venv）：
../.venv/bin/python ainiee_side_tests/test_http_handlers.py
```
