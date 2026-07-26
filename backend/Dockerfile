FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制 requirements 文件
COPY requirements.txt /app/root_requirements.txt
COPY backend/requirements.txt /app/backend_requirements.txt

# 安装 Python 依赖
RUN pip install --no-cache-dir -r /app/root_requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir -r /app/backend_requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用代码
COPY app.py /app/
COPY backend/ /app/backend/
COPY templates/ /app/templates/
COPY static/ /app/static/

# 创建数据目录
RUN mkdir -p /app/data

# 暴露端口
EXPOSE 5001

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/')" || exit 1

# 启动：通过导入 app 模块触发 init_db()，然后用环境变量控制 host/port
CMD ["sh", "-c", "python -c \"from app import app; app.run(host='${FLASK_HOST:-0.0.0.0}', port=int('${FLASK_PORT:-5001}'), debug=False)\""]