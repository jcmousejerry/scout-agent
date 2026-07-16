# Scout Agent - 一键启动脚本
param(
    [switch]$SkipIngest,
    [switch]$SkipGoBuild
)

$PYTHON = "D:\anaconda\envs\self_env_2\python.exe"
$ROOT = $PSScriptRoot

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Scout Agent 启动" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# --- 步骤 1: 初始化知识库（首次运行需要） ---
if (-not $SkipIngest) {
    $dbFile = Join-Path $ROOT "ai_agent\rag\scout_knowledge.db"
    if (-not (Test-Path $dbFile)) {
        Write-Host "`n[1/4] 初始化足球通识知识库向量..." -ForegroundColor Yellow
        & $PYTHON (Join-Path $ROOT "ai_agent\rag\ingest.py")
        if ($LASTEXITCODE -ne 0) {
            Write-Host "知识库初始化失败！" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "`n[1/4] 知识库已存在，跳过初始化" -ForegroundColor Green
    }
} else {
    Write-Host "`n[1/4] 跳过知识库初始化" -ForegroundColor DarkGray
}

# --- 步骤 2: 编译 Go 后端 ---
if (-not $SkipGoBuild) {
    Write-Host "`n[2/4] 编译 Go 后端..." -ForegroundColor Yellow
    Push-Location (Join-Path $ROOT "backend")
    go build -o scout-backend.exe .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Go 编译失败！" -ForegroundColor Red
        Pop-Location
        exit 2
    }
    Pop-Location
    Write-Host "  -> 编译成功" -ForegroundColor Green
} else {
    Write-Host "`n[2/4] 跳过 Go 编译" -ForegroundColor DarkGray
}

# --- 步骤 3: 启动 Python AI Agent (端口 8000) ---
Write-Host "`n[3/4] 启动 Python AI Agent (端口 8000)..." -ForegroundColor Yellow
$agentJob = Start-Job -ScriptBlock {
    param($py, $root)
    Set-Location $root
    & $py "ai_agent\api_server.py"
} -ArgumentList $PYTHON, $ROOT

Start-Sleep -Seconds 3
if ($agentJob.State -eq "Failed") {
    Write-Host "AI Agent 启动失败！" -ForegroundColor Red
    Receive-Job $agentJob
    exit 1
}
Write-Host "  -> http://localhost:8000 (FastAPI)" -ForegroundColor Green

# --- 步骤 4: 启动 Golang 后端 (端口 8080) ---
Write-Host "`n[4/4] 启动 Golang 后端 (端口 8080)..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location (Join-Path $root "backend")
    .\scout-backend.exe
} -ArgumentList $ROOT

Start-Sleep -Seconds 3
if ($backendJob.State -eq "Failed") {
    Write-Host "后端启动失败！" -ForegroundColor Red
    Receive-Job $backendJob
    Stop-Job $agentJob; Remove-Job $agentJob
    exit 1
}
Write-Host "  -> http://localhost:8080 (Gin)" -ForegroundColor Green

# --- 步骤 5: 启动 Next.js 前端 (端口 3000) ---
Write-Host "`n[5/4] 启动 Next.js 前端 (端口 3000)..." -ForegroundColor Yellow

$frontendDir = Join-Path $ROOT "frontend"
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "  安装前端依赖..." -ForegroundColor DarkGray
    Push-Location $frontendDir
    npm install --silent 2>&1 | Out-Null
    Pop-Location
}

$frontendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    npx next dev
} -ArgumentList $frontendDir

Start-Sleep -Seconds 5
Write-Host "  -> http://localhost:3000 (Next.js)" -ForegroundColor Green

# --- 完成 ---
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  所有服务已启动！" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  前端:  http://localhost:3000" -ForegroundColor White
Write-Host "  后端:  http://localhost:8080" -ForegroundColor White
Write-Host "  Agent: http://localhost:8000" -ForegroundColor White
Write-Host ""
Write-Host "  按 Ctrl+C 停止所有服务" -ForegroundColor DarkGray
Write-Host ""

# 等待用户中断
try {
    while ($true) {
        Start-Sleep -Seconds 2
        if ($agentJob.State -eq "Failed" -or $backendJob.State -eq "Failed" -or $frontendJob.State -eq "Failed") {
            Write-Host "`n[警告] 有服务异常退出：" -ForegroundColor Red
            if ($agentJob.State -eq "Failed") { Write-Host "  - AI Agent" -ForegroundColor Red; Receive-Job $agentJob 2>&1 | Select-Object -Last 5 }
            if ($backendJob.State -eq "Failed") { Write-Host "  - Backend" -ForegroundColor Red; Receive-Job $backendJob 2>&1 | Select-Object -Last 5 }
            if ($frontendJob.State -eq "Failed") { Write-Host "  - Frontend" -ForegroundColor Red; Receive-Job $frontendJob 2>&1 | Select-Object -Last 5 }
            break
        }
    }
} finally {
    Write-Host "`n正在停止所有服务..." -ForegroundColor Yellow
    @($agentJob, $backendJob, $frontendJob) | ForEach-Object {
        if ($_) { Stop-Job $_ -ErrorAction SilentlyContinue; Remove-Job $_ -ErrorAction SilentlyContinue }
    }
    Write-Host "已停止。" -ForegroundColor Green
}
