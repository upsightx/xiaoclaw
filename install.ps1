# xiaoclaw 一键安装脚本 (Windows PowerShell)
# 用法: irm https://raw.githubusercontent.com/upsightx/xiaoclaw/master/install.ps1 | iex
$ErrorActionPreference = "Stop"

function Write-Info  { Write-Host "[信息] $args" -ForegroundColor Cyan }
function Write-Ok    { Write-Host "[完成] $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "[警告] $args" -ForegroundColor Yellow }
function Write-Fail  { Write-Host "[错误] $args" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║     xiaoclaw 一键安装程序 v1.0       ║" -ForegroundColor Green
Write-Host "║   Lightweight AI Agent Installer     ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# ─── 检测/安装 Python ───
$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver) {
            $parts = $ver.Split(".")
            if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 10) {
                $python = $cmd
                break
            }
        }
    } catch {}
}

if (-not $python) {
    Write-Warn "未找到 Python 3.10+，正在自动安装..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        $python = "python"
    } else {
        Write-Fail "请先安装 Python 3.10+: https://www.python.org/downloads/"
    }
}

$pyver = & $python --version 2>&1
Write-Ok "Python 就绪: $pyver"

# ─── 检测 Git ───
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Warn "未找到 Git，正在安装..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install Git.Git --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    } else {
        Write-Fail "请先安装 Git: https://git-scm.com/download/win"
    }
}
Write-Ok "Git 就绪: $(git --version)"

# ─── 选择安装目录 ───
$defaultDir = "$env:USERPROFILE\xiaoclaw"
Write-Host ""
$installDir = Read-Host "[输入] 安装目录 [$defaultDir]"
if ([string]::IsNullOrWhiteSpace($installDir)) { $installDir = $defaultDir }

if ((Test-Path "$installDir\pyproject.toml")) {
    Write-Info "检测到已有安装，将更新..."
    Set-Location $installDir
    git pull origin master 2>$null
} else {
    Write-Info "正在下载 xiaoclaw..."
    git clone --depth 1 https://github.com/upsightx/xiaoclaw.git $installDir
    Set-Location $installDir
}
Write-Ok "代码就绪: $installDir"

# ─── 创建虚拟环境 ───
Write-Info "正在创建 Python 虚拟环境..."
if (-not (Test-Path ".venv")) {
    & $python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
Write-Ok "虚拟环境就绪"

# ─── 安装依赖 ───
Write-Info "正在安装依赖（可能需要 1-2 分钟）..."
pip install --upgrade pip -q 2>$null
pip install -r requirements.txt -q 2>$null
pip install -e . -q 2>$null
Write-Ok "依赖安装完成"

# ─── 交互式配置 ───
Write-Host ""
Write-Host "━━━ 配置向导 ━━━" -ForegroundColor Green
Write-Host ""

$skipConfig = $false
if (Test-Path "config.yaml") {
    $reconfig = Read-Host "[提示] 已有配置文件，是否重新配置？[y/N]"
    if ($reconfig -ne "y" -and $reconfig -ne "Y") {
        Write-Info "保留现有配置"
        $skipConfig = $true
    }
}

if (-not $skipConfig) {
    Write-Host "请选择 AI 模型提供商:"
    Write-Host "  1) OpenAI (GPT-4o)"
    Write-Host "  2) 自定义 OpenAI 兼容 API"
    Write-Host ""
    $choice = Read-Host "[选择] 请输入 [1-2，默认 2]"
    if ([string]::IsNullOrWhiteSpace($choice)) { $choice = "2" }

    switch ($choice) {
        "1" {
            $apiKey = Read-Host "[输入] OpenAI API Key"
            $baseUrl = "https://api.openai.com/v1"
            $model = "gpt-4o"
        }
        default {
            $baseUrl = Read-Host "[输入] API Base URL"
            if ([string]::IsNullOrWhiteSpace($baseUrl)) { $baseUrl = "https://api.openai.com/v1" }
            $apiKey = Read-Host "[输入] API Key"
            $model = Read-Host "[输入] 模型名称 [gpt-4o]"
            if ([string]::IsNullOrWhiteSpace($model)) { $model = "gpt-4o" }
        }
    }

    if ([string]::IsNullOrWhiteSpace($apiKey)) {
        Write-Warn "未提供 API Key，稍后可在 config.yaml 中配置"
        $apiKey = "your-api-key-here"
    }

    @"
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
    api_key: "$apiKey"
    base_url: "$baseUrl"
    default_model: "$model"
    models:
      - $model

skills_dir: "./skills"
"@ | Out-File -FilePath "config.yaml" -Encoding utf8
    Write-Ok "配置文件已生成: config.yaml"
}

# ─── 创建启动脚本 ───
@"
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m xiaoclaw %*
"@ | Out-File -FilePath "start.bat" -Encoding ascii

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║       ✅ xiaoclaw 安装完成！         ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  📁 安装目录: $installDir" -ForegroundColor Cyan
Write-Host "  ⚙️  配置文件: $installDir\config.yaml" -ForegroundColor Cyan
Write-Host ""
Write-Host "  启动方式:" -ForegroundColor White
Write-Host "    双击 start.bat" -ForegroundColor Green
Write-Host "    或在终端运行: .\start.bat" -ForegroundColor Green
Write-Host ""
Write-Host "  首次使用请确保 config.yaml 中的 API Key 已正确填写"
Write-Host ""
