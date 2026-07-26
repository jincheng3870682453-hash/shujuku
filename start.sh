#!/bin/bash
set -e

echo "========================================="
echo "  动态数据登记系统 - macOS/Linux 启动脚本"
echo "========================================="
echo ""

# 自动 chmod +x
chmod +x "$0" 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "请选择启动模式："
echo "  1) Web 版（Flask 后端 + 内嵌页面）"
echo "  2) 前后端分离开发（Flask + Vite dev server）"
echo "  3) Electron 桌面版"
echo ""
read -p "请输入选项 [1/2/3] (默认 1): " MODE
MODE=${MODE:-1}

# ==========================================
# 第一步：检查 Python 环境
# ==========================================
echo ""
echo "[检查] Python 环境..."
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ 未检测到 Python，请先安装 Python 3.10+"
    echo "   macOS:  brew install python3"
    echo "   Linux:  sudo apt install python3 python3-pip"
    exit 1
fi

PYVER=$(${PYTHON_CMD} --version 2>&1 | cut -d' ' -f2)
echo "        Python ${PYVER}"

PYMAJOR=$(echo ${PYVER} | cut -d'.' -f1)
if [ ${PYMAJOR} -lt 3 ]; then
    echo "❌ Python 版本过低，需要 3.10+"
    exit 1
fi

# ==========================================
# 第二步：安装 Python 依赖
# ==========================================
echo ""
echo "[安装] Python 依赖..."
cd "${SCRIPT_DIR}"
${PYTHON_CMD} -m pip install -r requirements.txt --quiet 2>/dev/null || {
    echo "       尝试使用清华镜像..."
    ${PYTHON_CMD} -m pip install -r requirements.txt --quiet -i https://pypi.tuna.tsinghua.edu.cn/simple 2>/dev/null
}
${PYTHON_CMD} -m pip install -r backend/requirements.txt --quiet 2>/dev/null || {
    ${PYTHON_CMD} -m pip install -r backend/requirements.txt --quiet -i https://pypi.tuna.tsinghua.edu.cn/simple 2>/dev/null
}
echo "       依赖检查完成"

# ==========================================
# 第三步：创建 backend/.env（如果不存在）
# ==========================================
if [ ! -f "${SCRIPT_DIR}/backend/.env" ]; then
    cat > "${SCRIPT_DIR}/backend/.env" << 'EOF'
DB_ENGINE=sqlite
SQLITE_PATH=./data/app.db
EOF
    echo "       已创建 backend/.env"
fi

# ==========================================
# 第四步：检查 Node.js（仅模式 2/3 需要）
# ==========================================
if [ "${MODE}" = "2" ] || [ "${MODE}" = "3" ]; then
    echo ""
    echo "[检查] Node.js 环境..."
    if ! command -v node &> /dev/null; then
        echo "❌ 未检测到 Node.js，模式 ${MODE} 需要 Node.js 20+"
        echo "   下载地址: https://nodejs.org/"
        exit 1
    fi
    echo "        Node.js $(node --version)"
fi

# ==========================================
# 第五步：按模式启动
# ==========================================
echo ""
echo "========================================="

case "${MODE}" in
    1)
        echo "  启动模式：Web 版"
        echo "  后端地址: http://localhost:5001"
        echo "  按 Ctrl+C 停止服务"
        echo "========================================="
        echo ""
        cd "${SCRIPT_DIR}"
        ${PYTHON_CMD} app.py
        ;;
    2)
        echo "  启动模式：前后端分离开发"
        echo "  后端地址: http://localhost:5001"
        echo "  前端地址: http://localhost:5173"
        echo "  按 Ctrl+C 停止全部服务"
        echo "========================================="
        echo ""

        # 安装前端依赖（如果需要）
        if [ ! -d "${SCRIPT_DIR}/frontend/node_modules" ]; then
            echo "[安装] 前端依赖..."
            cd "${SCRIPT_DIR}/frontend"
            npm install
            cd "${SCRIPT_DIR}"
        fi

        # 后台启动后端
        echo "[启动] 后端服务..."
        cd "${SCRIPT_DIR}"
        ${PYTHON_CMD} app.py &
        BACKEND_PID=$!

        # 等待后端就绪
        echo "[等待] 后端启动中（5秒）..."
        sleep 5

        # 启动前端
        echo "[启动] 前端 Vite dev server..."
        cd "${SCRIPT_DIR}/frontend"
        npx vite --host &
        FRONTEND_PID=$!

        cd "${SCRIPT_DIR}"

        # 等待用户 Ctrl+C，然后清理
        trap "echo ''; echo '正在停止服务...'; kill ${BACKEND_PID} 2>/dev/null; kill ${FRONTEND_PID} 2>/dev/null; echo '服务已停止'" EXIT INT TERM
        wait
        ;;
    3)
        echo "  启动模式：Electron 桌面版"
        echo "  后端将由 Electron 自动管理"
        echo "========================================="
        echo ""

        # 安装 Electron 依赖（如果需要）
        if [ ! -d "${SCRIPT_DIR}/electron/node_modules" ]; then
            echo "[安装] Electron 依赖..."
            cd "${SCRIPT_DIR}/electron"
            npm install
            cd "${SCRIPT_DIR}"
        fi

        # 编译 TypeScript（如果 dist 不存在）
        if [ ! -f "${SCRIPT_DIR}/electron/dist/main.js" ]; then
            echo "[编译] Electron TypeScript..."
            cd "${SCRIPT_DIR}/electron"
            npx tsc -p tsconfig.json
            if [ $? -ne 0 ]; then
                echo "❌ TypeScript 编译失败"
                exit 1
            fi
            cd "${SCRIPT_DIR}"
            echo "       编译完成"
        fi

        echo "[启动] Electron 桌面应用..."
        cd "${SCRIPT_DIR}/electron"
        npx electron dist/main.js
        ;;
    *)
        echo "❌ 无效选项，请输入 1、2 或 3"
        exit 1
        ;;
esac

echo ""
echo "应用已退出。"