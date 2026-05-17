#!/usr/bin/env bash
# Dramatica-Flow 一键安装脚本（Linux / macOS）

set -e

# 切换到脚本所在目录
cd "$(dirname "$0")"

echo ""
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║       Dramatica-Flow 一键安装脚本              ║"
echo "  ║       AI 长篇小说创作系统                      ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo ""

# ── 第一步：检查 Python ──────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 python3，请先安装 Python 3.11+"
    echo ""
    echo "  macOS (Homebrew):  brew install python@3.11"
    echo "  macOS (官网):      https://www.python.org/downloads/"
    echo "  Ubuntu/Debian:     sudo apt install python3 python3-pip python3-venv"
    echo "  Fedora:            sudo dnf install python3 python3-pip"
    echo ""
    # macOS 自动检测 Homebrew 并提示安装
    if [[ "$(uname)" == "Darwin" ]]; then
        if command -v brew &> /dev/null; then
            echo "  检测到已安装 Homebrew，可以直接运行："
            echo "    brew install python@3.11"
        else
            echo "  macOS 上推荐先安装 Homebrew："
            echo "    /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        fi
    fi
    echo ""
    exit 1
fi

echo "[1/6] 检测 Python 版本..."
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

echo "      当前版本：Python $PY_VER"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    echo ""
    echo "[错误] Python 版本过低！需要 3.11+，当前是 $PY_VER"
    echo "  请升级：https://www.python.org/downloads/"
    if [[ "$(uname)" == "Darwin" ]]; then
        echo "  macOS:  brew install python@3.11 && brew link python@3.11"
    fi
    echo ""
    exit 1
fi

echo "      版本检查通过 (需要 3.11+)"
echo ""

# ── 第二步：创建虚拟环境 ────────────────────────────────
VENV_DIR=".venv"

echo "[2/6] 配置虚拟环境..."
if [ -d "$VENV_DIR" ]; then
    echo "      虚拟环境已存在：$VENV_DIR，跳过创建"
else
    echo "      创建虚拟环境：$VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

# 激活虚拟环境
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    # Windows Git Bash 等环境
    source "$VENV_DIR/Scripts/activate"
else
    echo "[警告] 无法激活虚拟环境，将使用系统 Python"
fi

echo "      pip 版本：$(pip --version 2>/dev/null | head -1)"
echo ""

# ── 第三步：升级 pip ────────────────────────────────────
echo "[3/6] 升级 pip..."
pip install --upgrade pip -q 2>/dev/null || echo "      [警告] pip 升级失败，继续使用当前版本"
echo "      pip 升级完成"
echo ""

# ── 第四步：安装项目及依赖 ──────────────────────────────
echo "[4/6] 安装项目及依赖..."

# 完整的依赖列表（与 pyproject.toml 保持一致）
ALL_DEPS="openai pydantic typer rich python-dotenv fastapi uvicorn python-multipart"

if pip install -e . -q 2>/dev/null; then
    echo "      项目安装完成 (pip install -e .)"
else
    echo "[警告] pip install -e . 失败，直接安装依赖..."
    pip install $ALL_DEPS -q 2>/dev/null || {
        echo "[错误] 依赖安装失败，请检查网络或 Python 环境"
        exit 1
    }
fi
echo ""

# ── 第五步：逐个验证所有依赖 ────────────────────────────
echo "[5/6] 验证所有依赖..."

MISSING_COUNT=0

# 验证每个依赖包
for MOD in openai pydantic fastapi uvicorn typer rich dotenv; do
    if python3 -c "import $MOD" 2>/dev/null; then
        VER=$(python3 -c "import $MOD; print(getattr($MOD, '__version__', 'OK'))" 2>/dev/null)
        echo "      [OK] $MOD ($VER)"
    else
        echo "      [缺失] $MOD — 正在安装..."
        pip install "$MOD" -q 2>/dev/null && echo "      [已修复] $MOD 安装成功" || {
            echo "      [错误] $MOD 安装失败"
            MISSING_COUNT=$((MISSING_COUNT + 1))
        }
    fi
done

# 验证 python-multipart（模块名为 multipart）
if python3 -c "import multipart" 2>/dev/null; then
    VER=$(python3 -c "import multipart; print(getattr(multipart, '__version__', 'OK'))" 2>/dev/null)
    echo "      [OK] python-multipart ($VER)"
else
    echo "      [缺失] python-multipart — 正在安装..."
    pip install python-multipart -q 2>/dev/null && echo "      [已修复] python-multipart 安装成功" || {
        echo "      [错误] python-multipart 安装失败"
        MISSING_COUNT=$((MISSING_COUNT + 1))
    }
fi

# 验证 hatchling（构建工具）
if python3 -c "import hatchling" 2>/dev/null; then
    echo "      [OK] hatchling"
else
    echo "      [缺失] hatchling — 正在安装..."
    pip install hatchling -q 2>/dev/null && echo "      [已修复] hatchling 安装成功" || {
        echo "      [警告] hatchling 安装失败，不影响运行"
    }
fi

if [ $MISSING_COUNT -gt 0 ]; then
    echo ""
    echo "[错误] 有 $MISSING_COUNT 个依赖未能安装，请手动检查"
fi

if command -v df &> /dev/null; then
    echo "      CLI 命令 df 可用"
else
    echo "      [提示] df 命令暂不可用，可使用 Web UI 或 source .venv/bin/activate 后使用"
fi
echo ""

# ── 第六步：创建 .env ───────────────────────────────────
echo "[6/6] 检查配置文件..."
if [ -f .env ]; then
    echo "      .env 已存在，跳过"
elif [ -f .env.example ]; then
    cp .env.example .env
    echo "      已从 .env.example 创建 .env 文件"
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
    echo "      已创建 .env 文件"
fi

# ── 创建启动脚本 ────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 通用 start.sh
if [ ! -f "$SCRIPT_DIR/start.sh" ]; then
    cat > "$SCRIPT_DIR/start.sh" << 'EOF'
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo ""
echo "  正在启动 Dramatica-Flow Web UI..."
echo "  浏览器访问：http://localhost:8766"
echo ""

# 激活虚拟环境（如果存在）
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# 尝试自动打开浏览器
if command -v xdg-open &> /dev/null; then
    (sleep 2 && xdg-open http://localhost:8766) &
elif command -v open &> /dev/null; then
    (sleep 2 && open http://localhost:8766) &
fi

python3 -m uvicorn core.server:app --reload --port 8766
EOF
    chmod +x "$SCRIPT_DIR/start.sh"
fi

# ── 完成 ──────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  安装完成！"
echo ""
echo "  使用方法（需要先激活虚拟环境）："
echo "    source .venv/bin/activate"
echo "    ./start.sh"
echo ""
echo "    浏览器访问 http://localhost:8766"
echo ""
echo "  或者直接运行（自动激活虚拟环境）："
echo "    ./start.sh"
echo ""
echo "  首次使用必须配置 AI 接口（二选一）："
echo ""
echo "  方式一：DeepSeek API（效果最佳，需付费）"
echo "    1. 访问 https://platform.deepseek.com 注册"
echo "    2. 获取 API Key"
echo "    3. 编辑 .env，将 sk-xxx 替换为你的 API Key"
echo ""
echo "  方式二：Ollama 本地模型（完全免费）"
echo "    1. macOS:  brew install ollama"
echo "    2. 运行:   ollama pull qwen2.5"
echo "    3. 编辑 .env，将 LLM_PROVIDER 改为 ollama"
echo ""
echo "═══════════════════════════════════════════════════"
echo ""
