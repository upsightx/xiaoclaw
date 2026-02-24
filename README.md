# XiaClaw

Lightweight AI Agent - Minimal Core Design with Security First

## 特点

- 🏃 **轻量**: 核心代码 < 15K 行
- 🔒 **安全**: 默认禁用危险操作，按需开启
- 🔌 **兼容**: 兼容 OpenClaw 工具生态
- 🚀 **快速**: 启动 < 3秒

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python -m xiaoclaw.core
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| XIAOCLAW_DEBUG | 调试模式 | false |
| XIAOCLAW_SECURITY | 安全级别 | strict |
| XIAOCLAW_CONFIRM_DANGEROUS | 危险操作确认 | true |
| XIAOCLAW_MODEL | 默认模型 | minimax/MiniMax-M2.5 |

## 工具

- read - 读取文件
- write - 写入文件
- edit - 编辑文件
- exec - 执行命令
- web_search - 网页搜索
- web_fetch - 获取网页

## License

MIT
