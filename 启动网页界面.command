#!/usr/bin/env bash
# Dramatica-Flow macOS 双击启动脚本
# 在 Finder 中双击此文件即可启动 Web UI
# 
# 首次使用前请先运行 install_mac.sh 安装依赖

cd "$(dirname "$0")"

echo ""
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║    Dramatica-Flow — AI 长篇小说创作系统          ║"
echo "  ║    http://localhost:8766                        ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo ""

# ── 环境准备 ──────────────────────────────────────────────

# Homebrew 路径（Apple Silicon 芯片需要）
if [ -f /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# 激活虚拟环境
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "  [OK] 虚拟环境已激活"
else
    echo "  [!] 未找到虚拟环境 (.venv)"
    echo "  [!] 首次使用请先运行："
    echo "      chmod +x install_mac.sh && ./install_mac.sh"
    echo ""
    echo "  3 秒后尝试使用系统 Python 启动..."
    sleep 3
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo ""
    echo "  [错误] 未找到 Python！"
    echo "  请先安装 Python 3.11+："
    echo "    brew install python@3.11"
    echo ""
    echo "  按回车键退出..."
    read
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  [OK] Python $PY_VER"

# 快速检查关键依赖
MISSING_DEPS=()
for MOD in pydantic fastapi uvicorn python_multipart openai; do
    if ! python3 -c "import $MOD" 2>/dev/null; then
        MISSING_DEPS+=("$MOD")
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo ""
    echo "  [!] 缺少依赖: ${MISSING_DEPS[*]}"
    echo "  [!] 正在自动安装..."
    pip install -e . -q 2>/dev/null || pip install openai pydantic typer rich python-dotenv fastapi uvicorn python-multipart -q 2>/dev/null
    echo "  [OK] 依赖安装完成"
fi

echo ""
echo "  正在启动服务器..."
echo "  浏览器访问: http://localhost:8766"
echo "  按 Ctrl+C 停止服务器"
echo ""

# 自动打开浏览器
(sleep 3 && open http://localhost:8766) &

# 启动 uvicorn
python3 -m uvicorn core.server:app --reload --port 8766
