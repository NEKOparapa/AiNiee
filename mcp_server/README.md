# ainiee-mcp

English | [中文](README.zh.md)

A **universal** [MCP](https://modelcontextprotocol.io) server that lets **Claude Code** and
**Codex** drive [AiNiee](https://github.com/NEKOparapa/AiNiee): start/stop/monitor translation &
polish tasks, run analysis / glossary translation / API tests, manage `config.json` (interfaces,
glossary, prompts, languages, project type…), and **inspect & correct translation results — all
while AiNiee stays running** (no need to close it).

It works with **any text/project** AiNiee supports; it contains no project-specific correction
logic.

This is **Phase A**: the server talks to a *running* AiNiee over its HTTP service and edits
`config.json` directly. The backend is behind an `AiNieeBackend` seam so a future headless
in-process backend (Phase B) is a one-file addition.

> Paths below are written as `<AINIEE>/mcp_server`, where `<AINIEE>` is wherever you cloned
> AiNiee. Substitute your own absolute path (MCP clients need absolute paths in their config).

---

## 1. Enable AiNiee's HTTP service (one-time)

In AiNiee: **Settings → enable the HTTP listening service**, set the address (default
`127.0.0.1:3388`), then **restart AiNiee**. On startup the log lists the available endpoints.

## 2. Install the server

```bash
cd <AINIEE>/mcp_server          # the directory containing this README
python3 -m venv .venv
./.venv/bin/pip install -e .
```

(Its only runtime deps are `mcp` and `httpx`; it never imports AiNiee, so it stays lightweight
and independent of AiNiee's Python environment.)

## 3. Register with your client (stdio)

**Claude Code** — `claude mcp add`:
```bash
claude mcp add ainiee \
  --env AINIEE_HTTP_BASE_URL=http://127.0.0.1:3388 \
  -- <AINIEE>/mcp_server/.venv/bin/python -m ainiee_mcp.server
```
or a project-scoped `.mcp.json`:
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

**Codex** — `~/.codex/config.toml`:
```toml
[mcp_servers.ainiee]
command = "<AINIEE>/mcp_server/.venv/bin/python"
args = ["-m", "ainiee_mcp.server"]
env = { AINIEE_HTTP_BASE_URL = "http://127.0.0.1:3388", AINIEE_MCP_BACKEND = "http" }
```

### Environment variables
| var | default | meaning |
|---|---|---|
| `AINIEE_HTTP_BASE_URL` | `http://127.0.0.1:3388` | where AiNiee's HTTP service listens (match `http_listen_address`) |
| `AINIEE_HTTP_TIMEOUT` | `30` | per-request timeout (seconds) |
| `AINIEE_MCP_BACKEND` | `http` | backend kind (Phase A: `http`) |
| `AINIEE_CONFIG` | — | direct path to config.json (else auto-resolved) |
| `AINIEE_USER_DATA_DIR` / `AINIEE_REPO` | — | override config.json resolution (mirrors AiNiee's `FilePathConfig`) |

On macOS, config.json auto-resolves to `~/Library/Application Support/AiNiee/config.json`.

---

## Tools

**Translation control** — `ainiee_status`, `ainiee_translate`, `ainiee_polish`, `ainiee_stop`,
`ainiee_load_project`

**Extended tasks** (start → poll `*_result`) — `ainiee_analysis_start` / `ainiee_analysis_result`,
`ainiee_glossary_translate` / `ainiee_glossary_result`, `ainiee_api_test` / `ainiee_api_test_result`,
`ainiee_export`, `ainiee_save_cache`, `ainiee_get_analysis` (read a **loaded project's**
already-extracted character / term / non-translate tables straight from its cache — no re-run;
optional `kind` returns one slice)

**Config & resources** (edit `config.json`; safe while AiNiee runs) — `ainiee_get_config`
(keys redacted), `ainiee_list_platforms`, `ainiee_set_platform`, `ainiee_set_active_api`,
`ainiee_set_languages`, `ainiee_set_io_paths`, `ainiee_set_project_type`, `ainiee_set_glossary`,
`ainiee_set_exclusions`, `ainiee_set_pre_post_replacements`, `ainiee_set_characters`,
`ainiee_set_world_style`

**Universal translation correction** (live in-memory cache; no need to close AiNiee) —
`ainiee_cache_search`, `ainiee_cache_stats`, `ainiee_cache_update`, `ainiee_cache_replace`

`ainiee_cache_replace` takes generic rules `{find, replace, regex?, scope?, source_requires?,
skip_if_followed_by?}` and defaults to `dry_run=True` (preview first, then apply).
`source_requires` only replaces a translation when its **source** matches a pattern — a safe,
universal guard with no built-in domain rules.

### Concurrency
- **Config edits** are safe while AiNiee runs (atomic write; AiNiee re-reads at task start).
- **Cache edits** (`cache_update` / `cache_replace`) require AiNiee to be **running with a project
  loaded and not actively translating** (IDLE/STOPPED). They modify AiNiee's own in-memory cache and
  save — so there's **no need to close AiNiee** and no risk of overwrite. (The GUI's edit view may
  need a reload to show changes; the saved cache and any export reflect them.)

---

## Development

```bash
./.venv/bin/python -m pytest            # MCP server unit tests (run from mcp_server/)
# AiNiee-side handler tests + cross-process E2E (need AiNiee's venv):
../.venv/bin/python ainiee_side_tests/test_http_handlers.py
```
