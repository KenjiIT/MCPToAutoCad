param([int]$Port = 8769)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path $PSScriptRoot).Path
$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $listener) {
    Write-Output "No WiseKape MCP listener on port $Port."
    exit 0
}

$processIds = [System.Collections.Generic.List[int]]::new()
$currentId = [int]$listener.OwningProcess
while ($currentId -gt 0) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$currentId" -ErrorAction SilentlyContinue
    if (-not $proc -or -not $proc.CommandLine -or
        -not $proc.CommandLine.Contains($projectRoot) -or
        -not $proc.CommandLine.Contains('run-http.py')) {
        break
    }
    $processIds.Add($currentId)
    $currentId = [int]$proc.ParentProcessId
}
if ($processIds.Count -eq 0) {
    throw "Port $Port is owned by a process outside this WiseKape project; leaving it untouched."
}

foreach ($processId in $processIds) {
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 500
if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
    throw "WiseKape MCP still owns port $Port."
}
Write-Output "Stopped WiseKape MCP process tree on port $Port."
