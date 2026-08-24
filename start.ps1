# ============================================================
# Scout Agent - 一键启动所有服务
# 用法: 在项目根目录执行  .\start.ps1
#   可选参数:
#     -SkipIngest   跳过球探知识库向量初始化
#     -SkipGoBuild  跳过 Go 后端编译
# ============================================================
param(
    [switch]$SkipIngest,
    [switch]$SkipGoBuild
)

$ErrorActionPreference = "Stop"
$PYTHON = "D:\anaconda\envs\self_env_2\python.exe"
$ROOT = $PSScriptRoot

# 服务的进程名（用于 stop.ps1 按端口杀进程）
$PORTS = @{ GoBackend = 8080; MatchSim = 8001; AIAgent = 8000; Frontend = 3000 }

function Write-Step($i, $n, $msg) {
    Write-Host "`n[$i/$n] $msg" -ForegroundColor Yellow
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Scout Agent 一键启动" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# --- 前置检查：MySQL 是否可达 ---
Write-Step 0 5 "检查 MySQL (127.0.0.1:3306)..."
$mysqlUp = Test-NetConnection -ComputerName 127.0.0.1 -Port 3306 -WarningAction SilentlyContinue
if ($mysqlUp.TcpTestSucceeded) {
    Write-Host "  -> MySQL 端口可达" -ForegroundColor Green
} else {
    Write-Host "  -> [警告] MySQL 不可达！请先启动 MySQL 并创建 scout_agent 库" -ForegroundColor Red
    Write-Host "     继续？(Y/N)" -ForegroundColor Yellow
    $ans = Read-Host
    if ($ans -ne "Y" -and $ans -ne "y") { exit 1 }
}

# --- 步骤 1: 球探知识库向量初始化（首次运行或知识源变化后） ---
if (-not $SkipIngest) {
    $dbFile = Join-Path $ROOT "ai_agent\rag\scout_knowledge.db"
    $ingestScript = Join-Path $ROOT "ai_agent\rag\ingest.py"
    & $PYTHON $ingestScript --check 2>$null
    $indexIsCurrent = $LASTEXITCODE -eq 0
    if (-not $indexIsCurrent) {
        Write-Step 1 5 "初始化球探知识库向量..."
        & $PYTHON $ingestScript
        if ($LASTEXITCODE -ne 0) { Write-Host "知识库初始化失败！" -ForegroundColor Red; exit 2 }
        Write-Host "  -> 完成" -ForegroundColor Green
    } else {
        Write-Step 1 5 "球探知识库内容未变化，跳过初始化" -ForegroundColor DarkGray
    }
} else {
    Write-Step 1 5 "跳过知识库初始化" -ForegroundColor DarkGray
}

# --- 步骤 2: 编译 Go 后端 ---
if (-not $SkipGoBuild) {
    Write-Step 2 5 "编译 Go 后端..."
    Push-Location (Join-Path $ROOT "backend")
    go build -o scout-backend.exe .
    if ($LASTEXITCODE -ne 0) { Write-Host "Go 编译失败！" -ForegroundColor Red; Pop-Location; exit 3 }
    Pop-Location
    Write-Host "  -> 编译成功" -ForegroundColor Green
} else {
    Write-Step 2 5 "跳过 Go 编译" -ForegroundColor DarkGray
}

# --- 步骤 3: 启动 Go 后端 (8080) —— 必须最先，比赛模拟 seed 依赖它 ---
Write-Step 3 5 "启动 Go 后端 (端口 8080)..."
$backendDir = Join-Path $ROOT "backend"
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle='Scout - Go Backend :8080'; Set-Location '$backendDir'; Write-Host 'Go Backend 启动中...' -ForegroundColor Cyan; .\scout-backend.exe"
) -WindowStyle Normal
Write-Host "  -> 等待 Go 后端就绪..." -ForegroundColor DarkGray
Start-Sleep -Seconds 6

# --- 步骤 4: 启动比赛模拟 (8001) —— 它会通过 Go 把种子数据写入 MySQL ---
Write-Step 4 5 "启动比赛模拟 (端口 8001)..."
$matchDir = Join-Path $ROOT "match_sim"
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle='Scout - Match Sim :8001'; Set-Location '$matchDir'; Write-Host 'Match Sim 启动中...' -ForegroundColor Cyan; & '$PYTHON' api_server.py"
) -WindowStyle Normal
Start-Sleep -Seconds 4

# --- 步骤 5: 启动 AI 球探 (8000) ---
Write-Step 5 5 "启动 AI 球探 (端口 8000)..."
$agentDir = Join-Path $ROOT "ai_agent"
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle='Scout - AI Agent :8000'; Set-Location '$agentDir'; Write-Host 'AI Agent 启动中...' -ForegroundColor Cyan; & '$PYTHON' api_server.py"
) -WindowStyle Normal
Start-Sleep -Seconds 3

# --- 步骤 6: 启动前端 (3000) ---
$frontendDir = Join-Path $ROOT "frontend"
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "`n  首次运行，安装前端依赖..." -ForegroundColor DarkGray
    Push-Location $frontendDir
    npm install --silent 2>&1 | Out-Null
    Pop-Location
}
Write-Host "`n[6/5] 启动前端 (端口 3000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle='Scout - Frontend :3000'; Set-Location '$frontendDir'; Write-Host 'Frontend 启动中...' -ForegroundColor Cyan; npx next dev"
) -WindowStyle Normal
Start-Sleep -Seconds 5

# --- 完成 ---
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  所有服务已启动（各开一个窗口）" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  前端:        http://localhost:3000" -ForegroundColor White
Write-Host "  Go 后端:     http://localhost:8080" -ForegroundColor White
Write-Host "  AI 球探:     http://localhost:8000" -ForegroundColor White
Write-Host "  比赛模拟:    http://localhost:8001" -ForegroundColor White
Write-Host ""
Write-Host "  关闭所有服务:  .\stop.ps1" -ForegroundColor Magenta
Write-Host "  查看状态:      .\status.ps1" -ForegroundColor Magenta
Write-Host ""
Write-Host "  本窗口仅用于启动，可直接关闭。各服务窗口会显示实时日志。" -ForegroundColor DarkGray
Write-Host ""
