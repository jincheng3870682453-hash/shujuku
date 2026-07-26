# ============================================================
# 多阶段构建：前端 React + 后端 Flask 合为一个镜像
# ============================================================

# ---- Stage 1: 构建前端 ----
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# 复制 package 文件，利用 Docker 层缓存
COPY frontend/package.json frontend/package-lock.json ./

# 安装依赖（npm ci 更快且锁定版本）
RUN npm ci --registry=https://registry.npmmirror.com

# 复制前端源码
COPY frontend/ ./

# 构建生产版本
RUN npm run build


# ---- Stage 2: 后端运行镜像 ----
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制 Python 依赖文件
COPY requirements.txt /app/root_requirements.txt
COPY backend/requirements.txt /app/backend_requirements.txt

# 安装 Python 依赖（使用清华镜像加速）
RUN pip install --no-cache-dir -r /app/root_requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir -r /app/backend_requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制后端代码
COPY app.py /app/
COPY backend/ /app/backend/
COPY templates/ /app/templates/

# 从 Stage 1 复制前端构建产物到 static 目录（Flask serve）
COPY --from=frontend-builder /app/frontend/dist/ /app/static/

# 创建数据目录
RUN mkdir -p /app/data

# 暴露端口
EXPOSE 5001

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/')" || exit 1

# 启动：Waitress 生产模式
CMD ["sh", "-c", "python -c \"from waitress import serve; from app import app; serve(app, host='0.0.0.0', port=5001, threads=20)\""]
