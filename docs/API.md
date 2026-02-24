# xiaoclaw API Reference

Auto-generated documentation.


## __init__.py

Adapters - 平台适配器


#### Functions

- `get_telegram_adapter()` — 
- `get_discord_adapter()` — 
- `get_slack_adapter()` — 


## discord_adapter.py

xiaoclaw Discord Adapter — discord.py integration


### class `DiscordAdapter`

Bridges Discord messages to xiaoclaw.handle_message.

| Method | Args | Description |
|--------|------|-------------|
| `start` | `claw` | Start the Discord bot (blocking). Pass a XiaClaw instance. |


#### Functions

- `run_discord_bot(claw)` — Convenience: create adapter and run.


## feishu.py

Feishu Adapter - 飞书集成
兼容 OpenClaw 生态


### class `FeishuAdapter`

飞书适配器

| Method | Args | Description |
|--------|------|-------------|
| `get_tenant_access_token` | `` | 获取 tenant_access_token |
| `send_message` | `receive_id, message` | 发送消息 |
| `handle_webhook` | `payload` | 处理飞书 webhook 事件 |


#### Functions

- `get_feishu_client()` — 获取飞书客户端


## slack_adapter.py

xiaoclaw Slack Adapter — Slack Bolt integration


### class `SlackAdapter`

Bridges Slack messages to xiaoclaw.handle_message.

| Method | Args | Description |
|--------|------|-------------|
| `start` | `claw` | Start the Slack bot via Socket Mode (blocking). |


#### Functions

- `run_slack_bot(claw)` — Convenience: create adapter and run.


## telegram.py

xiaoclaw Telegram Adapter - python-telegram-bot integration


### class `TelegramAdapter`

Bridges Telegram messages to xiaoclaw.handle_message.

| Method | Args | Description |
|--------|------|-------------|
| `start` | `claw` | Start the Telegram bot (blocking). Pass a XiaClaw instance. |


#### Functions

- `run_telegram_bot(claw)` — Convenience: create adapter and run.


## api.py

xiaoclaw API Server — lightweight FastAPI-based HTTP interface


#### Functions

- `create_app(claw)` — Create FastAPI app wrapping a XiaClaw instance.
- `run_server(host, port)` — Run the API server.


## cli.py

xiaoclaw CLI — interactive terminal interface


#### Functions

- `async main()` — 


## core.py

xiaoclaw - Lightweight AI Agent compatible with OpenClaw ecosystem


### class `XiaClawConfig`

| Method | Args | Description |
|--------|------|-------------|
| `from_env` | `cls` |  |
| `from_yaml` | `cls, path` | Load from YAML file, env vars override. |


### class `SecurityManager`

| Method | Args | Description |
|--------|------|-------------|
| `is_dangerous` | `action` |  |
| `set_tool_whitelist` | `user_id, tools` | Set allowed tools for a user (empty = allow all). |
| `set_tool_blacklist` | `user_id, tools` | Set blocked tools for a user. |
| `is_tool_allowed` | `tool, user_id` | Check if a tool is allowed for a user. |
| `log_tool_call` | `tool, args` | Log tool invocations for audit. |


### class `RateLimiter`

Simple token-bucket rate limiter.

| Method | Args | Description |
|--------|------|-------------|
| `check` | `key` | Return True if allowed, False if rate-limited. |
| `remaining` | `key` |  |


### class `TokenStats`

Track token usage across sessions.

| Method | Args | Description |
|--------|------|-------------|
| `record` | `usage` | Record usage from an API response. |
| `record_tool` | `` |  |
| `summary` | `` |  |
| `reset` | `` |  |


### class `HookManager`

before_tool_call / after_tool_call / message_received hooks.

| Method | Args | Description |
|--------|------|-------------|
| `register` | `event, fn` |  |
| `async fire` | `event` |  |


### class `XiaClaw`

| Method | Args | Description |
|--------|------|-------------|
| `bootstrap_context` | `` | Lazy-loaded bootstrap context. |
| `async handle_message` | `message, user_id` | Process a user message, return full response. |
| `async handle_message_stream` | `message, user_id` | Process a user message, yield streaming chunks. |
| `health_check` | `` | Return health status for monitoring. |
| `reload_config` | `config_path` | Hot-reload configuration from file. |


## i18n.py

xiaoclaw i18n — minimal internationalization support


#### Functions

- `t(key, lang)` — Get translated string.


## memory.py

xiaoclaw Memory System - Compatible with OpenClaw memory format


### class `MemoryManager`

Manages MEMORY.md + memory/YYYY-MM-DD.md files.

| Method | Args | Description |
|--------|------|-------------|
| `memory_search` | `query, max_results` | Search MEMORY.md + memory/*.md for matching lines (keyword-based). |
| `memory_get` | `file_path, start_line, end_line` | Read specific lines from a memory file. |
| `read_memory` | `` | Read MEMORY.md content. |
| `read_daily` | `date` | Read memory/YYYY-MM-DD.md for given date (default: today). |
| `read_recent_daily` | `days` | Read recent daily memory files. |
| `write_memory` | `content` | Overwrite MEMORY.md. |
| `append_memory` | `text` | Append to MEMORY.md. |
| `append_daily` | `text, date` | Append to today's daily memory file. |
| `flush_important` | `messages, summary` | Save important info from messages before compaction. |
| `read_bootstrap_files` | `` | Read AGENTS.md, SOUL.md, USER.md, IDENTITY.md for system prompt. |


#### Functions

- `test_memory()` — Quick self-test.


## plugins.py

xiaoclaw Plugin System — discover and load pip-installable plugins


### class `PluginInfo`

Metadata about a loaded plugin.


### class `PluginManager`

Discovers and manages xiaoclaw plugins via entry_points.

| Method | Args | Description |
|--------|------|-------------|
| `discover` | `` | Discover installed plugins via entry_points (pip-installable). |
| `load_module` | `name, module_path` | Manually load a plugin from a module path. |
| `enable` | `name` |  |
| `disable` | `name` |  |
| `list_plugins` | `` |  |
| `get_all_tools` | `` | Get all tools from enabled plugins. |
| `get_all_hooks` | `` | Get all hooks from enabled plugins. |
| `apply_to_claw` | `claw` | Register all plugin tools and hooks with a XiaClaw instance. |


## providers.py

xiaoclaw Provider System - Multi-provider LLM management


### class `ProviderConfig`


### class `Provider`

Wraps an async LLM client for a single provider.

| Method | Args | Description |
|--------|------|-------------|
| `ready` | `` |  |
| `async chat` | `messages, model` |  |


### class `ProviderManager`

Manages multiple providers with runtime switching.

| Method | Args | Description |
|--------|------|-------------|
| `active` | `` |  |
| `add` | `config` |  |
| `switch` | `name` |  |
| `switch_model` | `model, provider_name` |  |
| `list_providers` | `` |  |
| `async chat_with_failover` | `messages` | Try active provider, failover to others on failure. |
| `async chat` | `messages` |  |
| `from_env` | `cls` | Load providers from environment variables. |
| `from_config` | `cls, config_path` | Load providers from config.yaml. |


#### Functions

- `test_providers()` — Quick self-test.


## session.py

xiaoclaw Session Management - JSONL persistence compatible with OpenClaw


### class `Session`

A single conversation session with JSONL persistence.

| Method | Args | Description |
|--------|------|-------------|
| `token_count` | `` |  |
| `add_message` | `role, content` |  |
| `save` | `` | Full save (rewrite entire file). |
| `load` | `` | Load session from JSONL file. |
| `clear` | `` |  |
| `get_context_window` | `max_tokens` | Get recent messages fitting within token budget, preserving tool call structure. |


### class `SessionManager`

Manages multiple sessions with list/restore/delete.

| Method | Args | Description |
|--------|------|-------------|
| `new_session` | `session_id` |  |
| `restore` | `session_id` |  |
| `list_sessions` | `` |  |
| `delete` | `session_id` |  |


#### Functions

- `count_tokens(text, model)` — Count tokens using tiktoken, fallback to char estimate.
- `count_messages_tokens(messages, model)` — 
- `test_session()` — Quick self-test.


## skills.py

xiaoclaw Skill System - Compatible with OpenClaw ClawHub format


### class `SkillMeta`

Metadata parsed from SKILL.md.


### class `Skill`


### class `SkillRegistry`

| Method | Args | Description |
|--------|------|-------------|
| `register` | `skill` |  |
| `get_skill` | `name` |  |
| `list_skills` | `` |  |
| `get_tool` | `name` |  |
| `list_tools` | `` |  |
| `activate_for_message` | `message` | Auto-activate skills based on user message. |
| `get_active_skills` | `` |  |
| `deactivate_all` | `` |  |
| `load_from_dir` | `skills_dir` | Load skills from directory. Supports both flat and nested layouts. |


#### Functions

- `parse_skill_md(content)` — Parse SKILL.md into SkillMeta. Compatible with OpenClaw ClawHub format.
- `should_activate(meta, user_message)` — Check if a skill should be activated based on user message.
- `create_skill(name, description, tools)` — 
- `register_builtin_skills(registry)` — Register built-in skills.
- `test_skills()` — Quick self-test.


## tools.py

xiaoclaw Tool Registry — built-in tools and OpenAI function definitions


### class `ToolRegistry`

| Method | Args | Description |
|--------|------|-------------|
| `get` | `name` |  |
| `list_names` | `` |  |
| `disable_tool` | `name` |  |
| `enable_tool` | `name` |  |
| `call` | `name, args` |  |
| `openai_functions` | `` |  |


## web.py

xiaoclaw Web Tools - real web_search and web_fetch implementations


#### Functions

- `web_search(query, count)` — Search via DuckDuckGo HTML (no API key needed).
- `web_fetch(url, max_chars)` — Fetch a URL and extract readable text content.
- `test_web()` — Quick self-test.


## webhook.py

xiaoclaw Webhook Server — receive HTTP callbacks and route to handlers


### class `WebhookHandler`

A registered webhook handler.


### class `WebhookServer`

Manages webhook endpoints. Integrates with FastAPI app.

| Method | Args | Description |
|--------|------|-------------|
| `register` | `name, path, callback, secret` | Register a webhook handler at a given path. |
| `unregister` | `name` |  |
| `list_handlers` | `` |  |
| `verify_signature` | `handler, body, signature` | Verify HMAC-SHA256 webhook signature. |
| `async dispatch` | `path, body, headers` | Dispatch incoming webhook to matching handler. |
| `get_event_log` | `limit` |  |
| `mount_on_app` | `app` | Mount webhook routes on a FastAPI app. |


#### Functions

- `github_webhook(payload, headers)` — Handle GitHub webhook events.
- `generic_webhook(payload, headers)` — Generic webhook handler — just logs the event.
