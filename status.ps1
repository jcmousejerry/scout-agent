# ============================================================
# Scout Agent - 查看各服务运行状态
# 用法: 在项目根目录执行  .\status.ps1
# ============================================================

$PORTS = @(
    @{ Port = 8080; Name = "Go 后端";  URL = "http://localhost:8080" },
    @{ Port = 8001; Name = "比赛模拟"; URL = "http://localhost:8001" },
    @{ Port = 8000; Name = "AI 球探";  URL = "http://localhost:8000" },
    @{ Port = 3000; Name = "前端";     URL = "http://localhost:3000" }
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Scout Agent 服务状态" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ("  {0,-8} {1,-10} {2,-7} {3}" -f "端口", "服务", "状态", "PID/进程") -ForegroundColor DarkGray
Write-Host "  -----------------------------------------------"

foreach ($s in $PORTS) {
    $conns = Get-NetTCPConnection -LocalPort $s.Port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        # 注意：$PID 是 PowerShell 只读自动变量（当前 shell 进程ID），不能赋值，改用 $procId
        $procId = $conns[0].OwningProcess
        $proc = try { (Get-Process -Id $procId -ErrorAction Stop).ProcessName } catch { "?" }
        Write-Host ("  {0,-8} {1,-10} {2,-7} {3} ({4})" -f $s.Port, $s.Name, "运行中", $procId, $proc) -ForegroundColor Green
    } else {
        Write-Host ("  {0,-8} {1,-10} {2}" -f $s.Port, $s.Name, "未运行") -ForegroundColor Red
    }
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  启动: .\start.ps1    关闭: .\stop.ps1" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Cyan
