#!/usr/bin/env bash
# xiaoclaw 一键安装脚本 (macOS / Linux)
# 用法: curl -fsSL https://raw.githubusercontent.com/upsightx/xiaoclaw/master/install.sh | bash
set -e

# ─── 颜色 ───
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[信息]${NC} $1"; }
ok()    { echo -e "${GREEN}[完成]${NC} $1"; }
warn()  { echo -e "${YELLOW}[警告]${NC} $1"; }
fail()  { echo -e "${RED}[错误]${NC} $1"; exit 1; }

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     xiaoclaw 一键安装程序 v1.0       ║${NC}"
echo -e "${GREEN}║   Lightweight AI Agent Installer     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""

# ─── 检测系统 ───
OS="$(uname -s)"
ARCH="$(uname -m)"
info "检测到系统: $OS ($ARCH)"

case "$OS" in
    Linux*)  PLATFORM="linux" ;;
    Darwin*) PLATFORM="macos" ;;
    *)       fail "不支持的系统: $OS（请使用 install.ps1 安装 Windows 版本）" ;;
esac

# ─── 检测/安装 Python ───
install_python() {
    info "正在安装 Python..."
    if [ "$PLATFORM" = "macos" ]; then
        if command -v brew &>/dev/null; then
            brew install python@3.12
        else
            info "先安装 Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            brew install python@3.12
        fi
    else
        if command -v apt-get &>/dev/null; then
            sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-pip python3-venv
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y python3 python3-pip
        elif command -v yum &>/dev/null; then
            sudo yum install -y python3 python3-pip
        elif command -v pacman &>/dev/null; then
            sudo pacman -Sy --noconfirm python python-pip
        else
            fail "无法自动安装 Python，请手动安装 Python 3.10+ 后重试"
        fi
    fi
}

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    warn "未找到 Python 3.10+，正在自动安装..."
    install_python
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    done
    [ -z "$PYTHON" ] && fail "Python 安装失败，请手动安装 Python 3.10+"
fi

PYVER=$("$PYTHON" --version 2>&1)
ok "Python 就绪: $PYVER"

# ─── 检测 Git ───
if ! command -v git &>/dev/null; then
    warn "未找到 Git，正在安装..."
    if [ "$PLATFORM" = "macos" ]; then
        xcode-select --install 2>/dev/null || brew install git
    else
        if command -v apt-get &>/dev/null; then
            sudo apt-get install -y -qq git
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y git
        fi
    fi
fi
ok "Git 就绪: $(git --version)"

# ─── 选择安装目录 ───
DEFAULT_DIR="$HOME/xiaoclaw"
echo ""
read -p "$(echo -e ${BLUE}[输入]${NC}) 安装目录 [$DEFAULT_DIR]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_DIR}"

if [ -d "$INSTALL_DIR" ] && [ -f "$INSTALL_DIR/pyproject.toml" ]; then
    info "检测到已有安装，将更新..."
    cd "$INSTALL_DIR"
    git pull origin master 2>/dev/null || true
else
    info "正在下载 xiaoclaw..."
    git clone --depth 1 https://github.com/upsightx/xiaoclaw.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi
ok "代码就绪: $INSTALL_DIR"

# ─── 创建虚拟环境 ───
info "正在创建 Python 虚拟环境..."
if [ ! -d ".venv" ]; then
    "$PYTHON" -m venv .venv
fi
source .venv/bin/activate
ok "虚拟环境就绪"

# ─── 安装依赖 ───
info "正在安装依赖（可能需要 1-2 分钟）..."
pip install --upgrade pip -q 2>/dev/null
pip install -r requirements.txt -q 2>/dev/null
pip install -e . -q 2>/dev/null
ok "依赖安装完成"

# ─── 交互式配置 ───
echo ""
echo -e "${GREEN}━━━ 配置向导 ━━━${NC}"
echo ""

SKIP_CONFIG=""
if [ -f "config.yaml" ]; then
    read -p "$(echo -e ${YELLOW}[提示]${NC}) 已有配置文件，是否重新配置？[y/N]: " RECONFIG
    if [ "$RECONFIG" != "y" ] && [ "$RECONFIG" != "Y" ]; then
        info "保留现有配置"
        SKIP_CONFIG=1
    fi
fi

if [ -z "$SKIP_CONFIG" ]; then
    echo "请选择 AI 模型提供商:"
    echo "  1) OpenAI (GPT-4o)"
    echo "  2) 自定义 OpenAI 兼容 API"
    echo ""
    read -p "$(echo -e ${BLUE}[选择]${NC}) 请输入 [1-2，默认 2]: " PROVIDER_CHOICE
    PROVIDER_CHOICE="${PROVIDER_CHOICE:-2}"

    case "$PROVIDER_CHOICE" in
        1)
            read -p "$(echo -e ${BLUE}[输入]${NC}) OpenAI API Key: " API_KEY
            BASE_URL="https://api.openai.com/v1"
            MODEL="gpt-4o"
            ;;
        *)
            read -p "$(echo -e ${BLUE}[输入]${NC}) API Base URL: " BASE_URL
            BASE_URL="${BASE_URL:-https://api.openai.com/v1}"
            read -p "$(echo -e ${BLUE}[输入]${NC}) API Key: " API_KEY
            read -p "$(echo -e ${BLUE}[输入]${NC}) 模型名称 [gpt-4o]: " MODEL
            MODEL="${MODEL:-gpt-4o}"
            ;;
    esac

    [ -z "$API_KEY" ] && { warn "未提供 API Key，稍后可在 config.yaml 中配置"; API_KEY="your-api-key-here"; }

    cat > config.yaml << YAML
# xiaoclaw 配置文件 (自动生成)
agent:
  debug: false
  security: strict
  workspace: "."
  max_context_tokens: 128000
  compaction_threshold: 6000

active_provider: default

providers:
  default:
    type: openai
    api_key: "$API_KEY"
    base_url: "$BASE_URL"
    default_model: "$MODEL"
    models:
      - $MODEL

skills_dir: "./skills"
YAML
    ok "配置文件已生成: config.yaml"
fi

# ─── 创建启动脚本 ───
cat > start.sh << 'STARTER'
#!/usr/bin/env bash
cd "$(dirname "$0")"
source .venv/bin/activate
python -m xiaoclaw "$@"
STARTER
chmod +x start.sh

# ─── 添加快捷命令 ───
SHELL_RC=""
[ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"
[ -z "$SHELL_RC" ] && [ -f "$HOME/.bashrc" ] && SHELL_RC="$HOME/.bashrc"

if [ -n "$SHELL_RC" ]; then
    if ! grep -q "alias xiaoclaw=" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# xiaoclaw" >> "$SHELL_RC"
        echo "alias xiaoclaw='$INSTALL_DIR/start.sh'" >> "$SHELL_RC"
        ok "已添加快捷命令 'xiaoclaw'（重开终端生效）"
    fi
fi

# ─── 完成 ───
echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       ✅ xiaoclaw 安装完成！         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "  📁 安装目录: ${BLUE}$INSTALL_DIR${NC}"
echo -e "  ⚙️  配置文件: ${BLUE}$INSTALL_DIR/config.yaml${NC}"
echo ""
echo -e "  启动方式:"
echo -e "    ${GREEN}cd $INSTALL_DIR && ./start.sh${NC}"
echo -e "    或重开终端后直接输入: ${GREEN}xiaoclaw${NC}"
echo ""
echo -e "  首次使用请确保 config.yaml 中的 API Key 已正确填写"
echo ""
