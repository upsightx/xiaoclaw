FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir pytest pytest-asyncio pytest-cov
COPY . .

ENV PYTHONUNBUFFERED=1
ENV XIAOCLAW_SECURITY=strict

CMD ["python", "-m", "xiaoclaw"]
