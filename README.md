# XiaClaw 🐾

Lightweight AI Agent — OpenClaw-compatible, minimal core, security first.

## v0.2.0 特性

- 🧠 **多Provider** — 支持多个LLM provider，运行时切换模型
- 💾 **Session持久化** — JSONL格式，兼容OpenClaw，支持恢复/列表/删除
- 📝 **Memory系统** — MEMORY.md + memory/YYYY-MM-DD.md，memory_search/memory_get
- 🗜️ **Compaction** — 对话超长时自动压缩，压缩前自动保存重要信息
- 📋 **Workspace Bootstrap** — 启动时读取 AGENTS.md/SOUL.md/USER.md/IDENTITY.md
- 🪝 **Hook系统** — before_tool_call / after_tool_call / message_received
- 🧩 **Skill系统** — SKILL.md解析，自动激活，兼容ClawHub格式
- 🔒 **安全** — 默认拦截危险命令，敏感路径保护

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
```

### pip

```bash
git clone https://github.com/upsightx/xiaoclaw.git && cd xiaoclaw
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m xiaoclaw
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | API密钥 | - |
| `OPENAI_BASE_URL` | API地址 | `https://ai.ltcraft.cn:12000/v1` |
| `XIAOCLAW_MODEL` | 模型 | `claude-opus-4-6` |
| `XIAOCLAW_SECURITY` | 安全级别 | `strict` |
| `XIAOCLAW_MAX_TOKENS` | 最大上下文token | `8000` |
| `XIAOCLAW_COMPACT_THRESHOLD` | 压缩阈值 | `6000` |
| `XIAOCLAW_WORKSPACE` | 工作目录 | `.` |

### 多Provider配置

```bash
# 主provider
export OPENAI_API_KEY=sk-xxx
export OPENAI_BASE_URL=https://api.example.com/v1

# 额外provider
export XIAOCLAW_PROVIDER_BACKUP_API_KEY=sk-yyy
export XIAOCLAW_PROVIDER_BACKUP_BASE_URL=https://backup.api/v1
export XIAOCLAW_PROVIDER_BACKUP_MODEL=gpt-4
```

## CLI命令

| 命令 | 说明 |
|------|------|
| `/tools` | 列出工具 |
| `/skills` | 列出Skills |
| `/model` | 查看/切换模型 |
| `/sessions` | 列出历史会话 |
| `/memory` | 查看记忆状态 |
| `/clear` | 新建会话 |
| `/quit` | 退出 |

## 自定义Skill

```python
# skills/myskill/skill.py
def my_tool(arg: str, **kw) -> str:
    return f"Result: {arg}"

def get_skill():
    from xiaoclaw.skills import create_skill
    return create_skill("myskill", "描述", {"my_tool": my_tool})
```

加上 `skills/myskill/SKILL.md` 支持自动激活：

```markdown
# My Skill
描述

## read_when
keyword1 keyword2
```

## 项目结构

```
xiaoclaw/
├── Dockerfile
├── requirements.txt
├── xiaoclaw/
│   ├── __init__.py
│   ├── __main__.py      # CLI入口
│   ├── core.py           # 核心引擎 (297行)
│   ├── providers.py      # 多Provider管理 (196行)
│   ├── session.py        # Session持久化 (218行)
│   ├── memory.py         # Memory系统 (219行)
│   └── skills.py         # Skill系统 (259行)
└── skills/               # 外部Skills
```

## 与OpenClaw对比

| | OpenClaw | XiaClaw |
|---|---|---|
| 代码 | 430K行 | ~1.2K行 |
| 启动 | 30s+ | <3s |
| 内存 | 1GB+ | <50MB |
| Session | JSONL ✅ | JSONL ✅ |
| Memory | MEMORY.md ✅ | MEMORY.md ✅ |
| Skills | ClawHub ✅ | 兼容 ✅ |
| Workspace | Bootstrap ✅ | Bootstrap ✅ |
| Compaction | ✅ | ✅ |
| 多Provider | ✅ | ✅ |
| Hook系统 | ✅ | ✅ |

## License

MIT
