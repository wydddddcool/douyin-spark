FROM python:3.11-slim

LABEL maintainer="douyin-spark"
LABEL description="抖音自动续火花脚本 + Web 控制面板"

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 安装 Playwright 系统依赖（必须先装 Python 包再装浏览器依赖）
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir flask \
    && playwright install chromium \
    && playwright install-deps chromium

# 复制项目
COPY . .

# 创建必要目录
RUN mkdir -p /app/auth /app/logs /app/config

# 时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 暴露 Web 面板端口
EXPOSE 5000

# 默认启动 Web 面板
CMD ["python", "web/app.py", "--host", "0.0.0.0", "--port", "5000"]
