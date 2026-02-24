# XiaClaw 🐾

Lightweight AI Agent — Minimal Core, Security First

> OpenClaw 太重？试试 XiaClaw。核心 < 1000 行，启动 < 3 秒，兼容 OpenClaw 生态。

## 特点

- 🏃 **轻量** — 核心代码 < 1000 行，依赖少
- 🔒 **安全** — 默认禁用危险操作，敏感路径保护
- 🔌 **兼容** — 兼容 OpenClaw Skill 格式
- 🧩 **插件化** — Skills 按需加载，自定义扩展简单
- 🤖 **多模型** — 支持 MiniMax / OpenAI / DeepSeek 等 OpenAI 兼容接口

---

## 快速开始

### 方式一：Docker（推荐）

```bash
# 克隆
git clone https://github.com/upsightx/xiaoclaw.git
cd xiaoclaw

# 构建
docker build -t xiaoclaw .

# 运行（交互模式）
docker run -it \
  -e OPENAI_API_KEY=your-api-key \
  -e OPENAI_BASE_URL=https://api.minimax.chat/v1 \
  -e XIAOCLAW_MODEL=MiniMax-M2.5 \
  xiaoclaw

# 运行测试
docker run --rm xiaoclaw python /app/test.py
```

### 方式二：pip 安装

```bash
git clone https://github.com/upsightx/xiaoclaw.git
cd xiaoclaw

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 运行
python -m xiaoclaw.core
```

### 方式三：直接使用

```bash
git clone https://github.com/upsightx/xiaoclaw.git
cd xiaoclaw
pip install aiohttp openai requests
python -m xiaoclaw.core
```

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | API 密钥 | - |
| `OPENAI_BASE_URL` | API 地址 | `https://api.minimax.chat/v1` |
| `XIAOCLAW_MODEL` | 默认模型 | `MiniMax-M2.5` |
| `XIAOCLAW_SECURITY` | 安全级别 | `strict` |
| `XIAOCLAW_DEBUG` | 调试模式 | `false` |
| `FEISHU_APP_ID` | 飞书 App ID | - |
| `FEISHU_APP_SECRET` | 飞书 App Secret | - |

---

## 使用方式

### 1. 作为 Python 库

```python
import asyncio
from xiaoclaw.core import XiaClaw, XiaClawConfig

async def main():
    # 创建配置
    config = XiaClawConfig(
        api_key="your-api-key",
        base_url="https://api.minimax.chat/v1",
        default_model="MiniMax-M2.5",
        security_level="strict"
    )

    # 初始化
    claw = XiaClaw(config)

    # 发送消息，获取 LLM 回复
    response = await claw.handle_message("你好，帮我写一个 Python hello world")
    print(response)

asyncio.run(main())
```

### 2. 使用内置工具

```python
from xiaoclaw.core import XiaClaw, XiaClawConfig

claw = XiaClaw(XiaClawConfig())

# 读取文件
result = claw.tools._tool_read("/etc/hostname")
print(result)

# 写入文件
claw.tools._tool_write("Hello XiaClaw!", "/tmp/test.txt")

# 执行命令
output = claw.tools._tool_exec("ls -la /tmp")
print(output)
```

### 3. 使用 Skills

```python
from xiaoclaw.core import XiaClaw, XiaClawConfig

claw = XiaClaw(XiaClawConfig())

# 查看已加载的 Skills
print(claw.skills.list_skills())
# ['weather', 'calculator', 'github', 'feishu']

# 调用天气
weather = claw.skills.get_tool("weather")
print(weather(location="Beijing"))

# 调用计算器
calc = claw.skills.get_tool("calc")
print(calc(expression="2 * 3 + 4"))
```

### 4. 自定义 Skill

在 `skills/` 目录下创建文件即可自动加载：

```python
# skills/translator/skill.py
def translate(text: str, to_lang: str = "en", **kwargs) -> str:
    # 你的翻译逻辑
    return f"Translated: {text}"

def get_skill():
    from xiaoclaw.skills import create_skill
    return create_skill(
        name="translator",
        description="文本翻译",
        tools={"translate": translate}
    )

skill = get_skill()
```

支持两种格式：
- `skills/xxx.py` — 单文件 Skill
- `skills/xxx/skill.py` — 目录 Skill（兼容 OpenClaw SKILL.md 格式）

---

## 内置工具

| 工具 | 说明 |
|------|------|
| `read` | 读取文件内容 |
| `write` | 写入文件 |
| `edit` | 编辑文件（查找替换） |
| `exec` | 执行 Shell 命令 |
| `web_search` | 网页搜索 |
| `web_fetch` | 获取网页内容 |

## 内置 Skills

| Skill | 工具 | 说明 |
|-------|------|------|
| calculator | `calc` | 数学计算 |
| weather | `weather`, `forecast` | 天气查询 |
| github | `gh` | GitHub CLI 操作 |
| feishu | `feishu_doc` | 飞书文档操作 |

---

## 安全机制

XiaClaw 默认启用严格安全模式：

- ❌ 自动拦截 `rm`、`del`、`format` 等危险命令
- ❌ 禁止访问 `~/.ssh`、`~/.gnupg`、`~/.aws` 等敏感路径
- ✅ 危险操作需要显式确认
- ✅ 命令执行超时保护（30s）

可通过 `XIAOCLAW_SECURITY` 调整：
- `strict` — 默认，最严格
- `normal` — 常规保护
- `relaxed` — 宽松模式

---

## 项目结构

```
xiaoclaw/
├── Dockerfile              # Docker 镜像
├── README.md
├── requirements.txt
├── config.example.yaml     # 配置示例
├── test.py                 # 测试脚本
├── xiaoclaw/
│   ├── __init__.py
│   ├── core.py             # 核心引擎 + LLM + 工具
│   ├── skills.py           # Skill 系统
│   └── adapters/
│       └── feishu.py       # 飞书适配器
└── skills/
    ├── weather.py           # 天气 Skill
    ├── github/              # GitHub Skill
    │   ├── SKILL.md
    │   └── skill.py
    └── feishu/              # 飞书 Skill
        ├── SKILL.md
        └── skill.py
```

---

## 与 OpenClaw 对比

| | OpenClaw | XiaClaw |
|---|---|---|
| 代码量 | 430K 行 | < 1K 行 |
| 启动时间 | 30s+ | < 3s |
| 内存占用 | 1GB+ | < 50MB |
| 安全模式 | 后置 | 默认严格 |
| Skill 兼容 | ✅ | ✅ |
| 学习成本 | 高 | 低 |

---

## License

MIT
