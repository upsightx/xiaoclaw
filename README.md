# xiaoclaw 🐾

Lightweight AI Agent — OpenClaw-compatible, minimal core, security first.

## 一键安装

无需任何开发经验，复制粘贴一行命令即可完成安装。

**macOS / Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/upsightx/xiaoclaw/master/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/upsightx/xiaoclaw/master/install.ps1 | iex
```

安装脚本会自动：
- ✅ 检测并安装 Python 3.10+ 和 Git
- ✅ 创建独立虚拟环境（不污染系统）
- ✅ 安装所有依赖
- ✅ 启动交互式配置向导（选模型、填 API Key）
- ✅ 生成启动脚本和快捷命令

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

## 手动安装

### Docker

```bash
git clone https://github.com/upsightx/xiaoclaw.git && cd xiaoclaw
docker build -t xiaoclaw .

# 交互模式
docker run -it \
  -e OPENAI_API_KEY=your-key \
  -e OPENAI_BASE_URL=https://api.example.com/v1 \
  -e XIAOCLAW_MODEL=your-model \
  xiaoclaw
```

### pip

**Ubuntu/Debian 用户：** 安装前请先安装 python3-venv：

```bash
sudo apt update && sudo apt install python3-venv -y
```

然后执行标准安装流程：

```bash
git clone https://github.com/upsightx/xiaoclaw.git && cd xiaoclaw
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[all,dev]"
xiaoclaw          # 首次运行会启动设置向导
xiaoclaw --setup  # 重新运行设置向导
```

### Web UI（推荐新手）

一键启动浏览器界面：

```bash
xiaoclaw --web
```

浏览器访问 http://localhost:8080 即可使用。支持：
- 💬 现代化聊天界面
- 🎨 Markdown 渲染 + 代码高亮
- ⚙️ 在线设置（API Key、模型等）
- 📊 Token 统计实时显示


```bash
git clone https://github.com/upsightx/xiaoclaw.git && cd xiaoclaw
pip install -e ".[all,dev]"
xiaoclaw          # 首次运行会启动设置向导
xiaoclaw --setup  # 重新运行设置向导
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
| `/battle <问题>` | | 多角色辩论 |
| `/battle-roles` | | 查看预设角色 |
| `/battle-custom <角色> <问题>` | | 自定义角色辩论 |
| `/clear` | `/c` | 新建会话 |
| `/version` | `/v` | 查看版本 |
| `/setup` | | 重新运行设置向导 |
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
├── install.sh              # 一键安装 (macOS/Linux)
├── install.ps1             # 一键安装 (Windows)
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
│   ├── battle.py           # 多角色辩论引擎
│   ├── subagent.py         # 子Agent并行任务
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

## 故障排查

### 常见问题

**Q: 运行 `xiaoclaw --web` 提示依赖缺失**

```bash
# Web UI 需要额外依赖
pip install xiaoclaw[web]
# 或安装全部功能
pip install xiaoclaw[all]
```

**Q: 首次运行显示 "API Key 未配置"**

运行设置向导配置：
```bash
xiaoclaw --setup
```
或直接设置环境变量：
```bash
export OPENAI_API_KEY=sk-your-key
export OPENAI_BASE_URL=https://api.openai.com/v1  # 可选
export XIAOCLAW_MODEL=gpt-4  # 可选
```

**Q: Ubuntu/Debian 创建虚拟环境失败**

```bash
sudo apt install python3-venv -y
```

**Q: Windows PowerShell 执行策略错误**

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Q: 未知选项错误**

检查命令格式：
```bash
xiaoclaw --help  # 查看可用选项
```

### 调试模式

启用详细日志排查问题：
```bash
xiaoclaw --debug
# 或设置日志级别
xiaoclaw --log-level DEBUG
```

### 自检测试

运行内置测试验证安装：
```bash
xiaoclaw --test
```

## License

MIT
