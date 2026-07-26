# ============================================================
# Scout Agent - 一键关闭所有服务
# 按端口精准杀掉监听 8000/8001/8080/3000 的进程
# 用法: 在项目根目录执行  .\stop.ps1
# ============================================================

$PORTS = @(8080, 8001, 8000, 3000)
$NAMES = @{ 8080 = "Go 后端"; 8001 = "比赛模拟"; 8000 = "AI 球探"; 3000 = "前端" }

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Scout Agent 一键关闭" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$killed = 0
foreach ($port in $PORTS) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
        Write-Host ("  端口 {0,-5} ({1})  未在运行" -f $port, $NAMES[$port]) -ForegroundColor DarkGray
        continue
    }
    foreach ($c in $conns) {
        # 注意：$PID 是 PowerShell 只读自动变量（当前 shell 进程ID），不能赋值，改用 $procId
        $procId = $c.OwningProcess
        try {
            $proc = Get-Process -Id $procId -ErrorAction Stop
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            Write-Host ("  端口 {0,-5} ({1})  已停止  PID={2} ({3})" -f $port, $NAMES[$port], $procId, $proc.ProcessName) -ForegroundColor Green
            $killed++
        } catch {
            Write-Host ("  端口 {0,-5} ({1})  进程已不存在" -f $port, $NAMES[$port]) -ForegroundColor DarkGray
        }
    }
}

Write-Host "`n============================================" -ForegroundColor Cyan
if ($killed -gt 0) {
    Write-Host "  已停止 $killed 个服务" -ForegroundColor Green
} else {
    Write-Host "  没有正在运行的服务" -ForegroundColor DarkGray
}
Write-Host "============================================" -ForegroundColor Cyan
