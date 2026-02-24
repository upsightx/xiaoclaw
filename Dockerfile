FROM python:3.12-slim

LABEL maintainer="xiaoclaw"
LABEL description="XiaClaw - Lightweight AI Agent"

# 设置工作目录
WORKDIR /app

# 复制代码
COPY . .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV XIAOCLAW_SECURITY=strict
ENV XIAOCLAW_CONFIRM_DANGEROUS=true

# 默认命令
CMD ["python", "-m", "xiaoclaw.core"]
