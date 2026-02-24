# xiaoclaw 🐾

Lightweight AI Agent — OpenClaw-compatible, minimal core, security first.

## v0.3.1 特性

### 核心
- 🤖 **多Provider** — 支持多个LLM provider，运行时切换，自动failover
- 💾 **Session持久化** — JSONL格式，兼容OpenClaw，支持恢复/列表/删除
- 📝 **Memory系统** — MEMORY.md + memory/YYYY-MM-DD.md，memory_search/memory_get
- 🗜️ **LLM Compaction** — 对话超长时用LLM智能摘要压缩
- 📋 **Workspace Bootstrap** — 启动时读取 AGENTS.md/SOUL.md/USER.md/IDENTITY.md
- 🪝 **Hook系统** — before_tool_call / after_tool_call / message_received
- 🧩 **Skill系统** — SKILL.md解析，自动激活，兼容ClawHub格式
- 🔒 **安全** — 默认拦截危险命令，审计日志，工具权限控制

### 智能
- 🌐 **i18n** — 多语言UI支持 (中/英)
- 📝 **Prompt模板** — 自定义系统提示词 (.xiaoclaw/prompt.txt)
- 🔢 **内置Skills** — 计算器、时间/时区、安全Python执行、翻译

### 服务器
- 🌍 **API Server** — FastAPI HTTP接口 (/chat, /tools, /stats, /sessions)
- ❤️ **Health Check** — /healthz 健康检查端点
- 🔗 **Webhook Server** — 接收HTTP回调，支持GitHub webhook等

### 适配器
- 📱 **Telegram** — python-telegram-bot集成
- 💬 **Discord** — discord.py集成
- 💼 **Slack** — slack-bolt Socket Mode集成
- 🐦 **飞书** — 飞书开放平台集成

### 性能
- ⚡ **并行工具调用** — 多个tool call异步并行执行
- 🧠 **懒加载** — Bootstrap context按需加载，减少启动内存
- 👥 **多用户会话** — 并发session支持，每个用户独立会话

### 扩展
- 🔌 **Plugin系统** — pip-installable插件，entry_points自动发现
- 🔄 **Config热重载** — 监控config.yaml变更，自动重载
- 🛡️ **工具权限** — 按用户whitelist/blacklist控制工具访问

### DevOps
- 🏗️ **CI/CD** — GitHub Actions: lint + pytest + Docker build
- 🧪 **36个测试** — pytest + coverage，覆盖所有核心模块
- 📄 **自动文档** — API文档自动生成 (scripts/gendocs.py)

## 快速开始

### Docker（推荐）

```bash
git clone https://github.com/upsightx/xiaoclaw.git && cd xiaoclaw

docker build -t xiaoclaw .

# 交互模式
docker run -it \
  -e OPENAI_API_KEY=your-key \
  -e OPENAI_BASE_URL=https://api.example.com/v1 \
  -e XIAOCLAW_MODEL=your-model \
  xiaoclaw

# 测试
docker run --rm -e OPENAI_API_KEY=xxx -e OPENAI_BASE_URL=xxx -e XIAOCLAW_MODEL=xxx \
  xiaoclaw python -m xiaoclaw --test

# pytest
docker run --rm xiaoclaw pytest tests/ -v
```

### pip

```bash
git clone https://github.com/upsightx/xiaoclaw.git && cd xiaoclaw
pip install -e ".[all,dev]"
xiaoclaw
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | API密钥 | - |
| `OPENAI_BASE_URL` | API地址 | `https://ai.ltcraft.cn:12000/v1` |
| `XIAOCLAW_MODEL` | 模型 | `claude-opus-4-6` |
| `XIAOCLAW_SECURITY` | 安全级别 | `strict` |
| `XIAOCLAW_MAX_TOKENS` | 最大上下文token | `128000` |
| `XIAOCLAW_LANG` | UI语言 (zh/en) | `zh` |

### 多Provider配置

```bash
export OPENAI_API_KEY=sk-xxx
export XIAOCLAW_PROVIDER_BACKUP_API_KEY=sk-yyy
export XIAOCLAW_PROVIDER_BACKUP_BASE_URL=https://backup.api/v1
export XIAOCLAW_PROVIDER_BACKUP_MODEL=gpt-4
```

## CLI命令

| 命令 | 别名 | 说明 |
|------|------|------|
| `/tools` | `/t` | 列出工具 |
| `/skills` | | 列出Skills |
| `/skill on/off <name>` | | 启用/禁用Skill |
| `/model` | | 查看Provider/模型 |
| `/sessions` | `/s` | 列出历史会话 |
| `/restore <id>` | | 恢复会话 |
| `/export [md/json]` | | 导出会话 |
| `/memory` | `/m` | 查看记忆状态 |
| `/stats` | | Token统计 |
| `/loglevel <level>` | | 设置日志级别 |
| `/reload` | | 热重载配置 |
| `/clear` | `/c` | 新建会话 |
| `/quit` | `/q` | 退出 |

## Plugin开发

```python
# xiaoclaw_myplugin/__init__.py
__version__ = "0.1.0"
__description__ = "My xiaoclaw plugin"

TOOLS = {
    "my_tool": lambda text, **kw: f"Result: {text}",
}

# pyproject.toml
[project.entry-points."xiaoclaw.plugins"]
myplugin = "xiaoclaw_myplugin"
```

## 自定义Skill

```python
# skills/myskill/skill.py
def my_tool(arg: str, **kw) -> str:
    return f"Result: {arg}"

def get_skill():
    from xiaoclaw.skills import create_skill
    return create_skill("myskill", "描述", {"my_tool": my_tool})
```

## 项目结构

```
xiaoclaw/
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── tests/
│   └── test_xiaoclaw.py    # 36 pytest tests
├── scripts/
│   └── gendocs.py          # API doc generator
├── docs/
│   └── API.md              # Auto-generated API docs
├── xiaoclaw/
│   ├── core.py             # 核心引擎
│   ├── providers.py        # 多Provider管理
│   ├── session.py          # Session持久化
│   ├── memory.py           # Memory系统
│   ├── skills.py           # Skill系统
│   ├── tools.py            # 工具注册
│   ├── web.py              # Web搜索/抓取
│   ├── api.py              # FastAPI服务
│   ├── webhook.py          # Webhook服务
│   ├── plugins.py          # Plugin系统
│   ├── i18n.py             # 国际化
│   ├── cli.py              # CLI界面
│   └── adapters/
│       ├── telegram.py     # Telegram适配器
│       ├── discord_adapter.py  # Discord适配器
│       ├── slack_adapter.py    # Slack适配器
│       └── feishu.py       # 飞书适配器
└── skills/                 # 外部Skills
    ├── weather.py
    ├── github/
    └── feishu/
```

## License

MIT
