#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# Dramatica-Flow macOS 一键安装脚本
# 双击即可运行，或在终端执行: chmod +x install_mac.sh && ./install_mac.sh
# ═══════════════════════════════════════════════════════════

set -e

cd "$(dirname "$0")"

echo ""
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║    Dramatica-Flow macOS 安装脚本                 ║"
echo "  ║    AI 长篇小说创作系统                           ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo ""

# ── 第一步：检查 Homebrew ─────────────────────────────────
echo "[1/7] 检查 Homebrew..."
if command -v brew &> /dev/null; then
    echo "      Homebrew 已安装"
else
    echo "      未检测到 Homebrew，正在安装..."
    echo "      （需要输入管理员密码）"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Apple Silicon 芯片需要额外配置 PATH
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo "      Homebrew 安装完成 (Apple Silicon)"
    elif [ -f /usr/local/bin/brew ]; then
        echo "      Homebrew 安装完成 (Intel)"
    else
        echo "[警告] Homebrew 安装可能未成功，继续尝试..."
    fi
fi
echo ""

# ── 第二步：检查 Python ──────────────────────────────────
echo "[2/7] 检查 Python..."

# Apple Silicon PATH 修正
if [ -f /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# 优先使用 Homebrew 的 Python
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
elif command -v python3.13 &> /dev/null; then
    PYTHON_CMD="python3.13"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "[错误] 未找到 Python，正在通过 Homebrew 安装..."
    brew install python@3.11
    if [ -f /opt/homebrew/bin/python3.11 ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    PYTHON_CMD="python3.11"
fi

PY_VER=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
PY_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")

echo "      Python: $PYTHON_CMD ($PY_VER)"
echo "      路径: $($PYTHON_CMD -c "import sys; print(sys.executable)")"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    echo ""
    echo "[错误] Python 版本过低！需要 3.11+，当前是 $PY_VER"
    echo "  正在通过 Homebrew 升级..."
    brew install python@3.11
    if [ -f /opt/homebrew/bin/python3.11 ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    PYTHON_CMD="python3.11"
    PY_VER=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "  升级后: Python $PY_VER"
fi

echo "      版本检查通过 (需要 3.11+)"
echo ""

# ── 第三步：创建虚拟环境 ────────────────────────────────
VENV_DIR=".venv"

echo "[3/7] 配置虚拟环境..."
if [ -d "$VENV_DIR" ]; then
    echo "      虚拟环境已存在：$VENV_DIR"
else
    echo "      创建虚拟环境..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo "      虚拟环境已创建：$VENV_DIR"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"
echo "      已激活虚拟环境"
echo "      pip: $(pip --version 2>/dev/null | head -1)"
echo ""

# ── 第四步：升级 pip ────────────────────────────────────
echo "[4/7] 升级 pip..."
pip install --upgrade pip -q 2>/dev/null || echo "      [警告] pip 升级跳过"
echo "      完成"
echo ""

# ── 第五步：安装项目及依赖 ──────────────────────────────
echo "[5/7] 安装项目及依赖..."

# 完整依赖列表
ALL_DEPS="openai pydantic typer rich python-dotenv fastapi uvicorn python-multipart hatchling"

if pip install -e . -q 2>/dev/null; then
    echo "      pip install -e . 成功"
else
    echo "      [回退] 直接安装依赖包..."
    pip install $ALL_DEPS -q 2>/dev/null || {
        echo "[错误] 依赖安装失败！请检查网络连接"
        echo "  可尝试手动运行："
        echo "    source .venv/bin/activate"
        echo "    pip install openai pydantic typer rich python-dotenv fastapi uvicorn python-multipart hatchling"
        exit 1
    }
fi
echo ""

# ── 第六步：逐个验证依赖 ────────────────────────────────
echo "[6/7] 验证依赖..."

MISSING=0
for MOD in openai pydantic fastapi uvicorn typer rich dotenv multipart hatchling; do
    if python3 -c "import $MOD" 2>/dev/null; then
        VER=$(python3 -c "import $MOD; v=getattr($MOD, '__version__', ''); print(v if v else 'OK')" 2>/dev/null)
        echo "      OK  $MOD ($VER)"
    else
        echo "      !!  $MOD 缺失 — 安装中..."
        # multipart 对应的 pip 包名
        if [ "$MOD" = "multipart" ]; then
            PIP_NAME="python-multipart"
        else
            PIP_NAME="$MOD"
        fi
        pip install "$PIP_NAME" -q 2>/dev/null && echo "      OK  $MOD 已修复" || {
            echo "      XX  $MOD 安装失败"
            MISSING=$((MISSING + 1))
        }
    fi
done

if [ $MISSING -gt 0 ]; then
    echo ""
    echo "[错误] $MISSING 个依赖安装失败"
fi

# CLI 命令检查
if command -v df &> /dev/null; then
    echo "      CLI 命令 df 可用"
else
    echo "      [提示] df 命令暂不可用，可通过 Web UI 操作所有功能"
fi
echo ""

# ── 第七步：创建 .env ───────────────────────────────────
echo "[7/7] 配置文件..."
if [ -f .env ]; then
    echo "      .env 已存在"
elif [ -f .env.example ]; then
    cp .env.example .env
    echo "      已创建 .env（来自 .env.example）"
else
    cat > .env << 'EOF'
# Dramatica-Flow 配置
LLM_PROVIDER=deepseek

# DeepSeek 配置（需要填入你的 API Key）
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# Ollama 本地模型配置（免费，零成本）
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434/v1
# OLLAMA_MODEL=llama3.1
EOF
    echo "      已创建 .env"
fi

# ── 创建 macOS 专用启动脚本 (.command 可双击) ─────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$SCRIPT_DIR/启动网页界面.command" << LAUNCHEOF
#!/usr/bin/env bash
cd "$(dirname "\$0")"
echo ""
echo "  ═══════════════════════════════════════"
echo "    Dramatica-Flow Web UI"
echo "    浏览器访问: http://localhost:8766"
echo "  ═══════════════════════════════════════"
echo ""
echo "  启动中，请稍候..."
echo "  （按 Ctrl+C 可停止服务器）"
echo ""

# Homebrew 路径
if [ -f /opt/homebrew/bin/brew ]; then
    eval "\$(/opt/homebrew/bin/brew shellenv)"
fi

# 激活虚拟环境
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# 自动打开浏览器
(sleep 3 && open http://localhost:8766) &

python3 -m uvicorn core.server:app --reload --port 8766
LAUNCHEOF
chmod +x "$SCRIPT_DIR/启动网页界面.command"
echo "      已创建启动脚本: 启动网页界面.command"

# ── 完成 ──────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo ""
echo "  安装完成！"
echo ""
echo "  启动方式（二选一）："
echo ""
echo "  A) 在 Finder 中双击「启动网页界面.command」"
echo "     浏览器会自动打开 http://localhost:8766"
echo ""
echo "  B) 终端启动："
echo "     source .venv/bin/activate"
echo "     ./start.sh"
echo ""
echo "  首次使用必须配置 AI 接口（二选一）："
echo ""
echo "  方式一：DeepSeek API（效果最佳，需付费）"
echo "    1. 访问 https://platform.deepseek.com 注册"
echo "    2. 获取 API Key"
echo "    3. 编辑 .env，将 sk-xxx 替换为你的 API Key"
echo ""
echo "  方式二：Ollama 本地模型（完全免费）"
echo "    1. brew install ollama"
echo "    2. ollama pull qwen2.5"
echo "    3. 编辑 .env，将 LLM_PROVIDER 改为 ollama"
echo ""
echo "═══════════════════════════════════════════════════"
echo ""
