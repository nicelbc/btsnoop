#!/bin/bash
# 一键启动 btsnoop-web（开发模式）
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== btsnoop-web 启动 ==="
echo ""

# 检查 Python 依赖
echo "[1/3] 检查后端依赖..."
cd "$SCRIPT_DIR/backend"
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "  安装 Python 依赖..."
    pip3 install -r requirements.txt -q
fi
echo "  ✓ 后端依赖就绪"

# 检查前端依赖
echo "[2/3] 检查前端依赖..."
cd "$SCRIPT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    echo "  安装 npm 依赖..."
    npm install --silent
fi
echo "  ✓ 前端依赖就绪"

# 启动
echo "[3/3] 启动服务..."
echo ""
echo "  后端: http://localhost:8000"
echo "  前端: http://localhost:5173"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo ""

# 启动后端
cd "$SCRIPT_DIR/backend"
python3 server.py &
BACKEND_PID=$!

# 启动前端
cd "$SCRIPT_DIR/frontend"
npx vite --host 2>/dev/null &
FRONTEND_PID=$!

# 等待退出
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
