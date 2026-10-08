param([int]$Port = 8770, [switch]$Background)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run .\setup-local.ps1 first.' }
if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) { throw "Port $Port already in use." }
$arguments = @('-u', 'http_host.py', '--host', '127.0.0.1', '--port', "$Port")
if ($Background) {
    $data = Join-Path $PSScriptRoot 'data'
    New-Item -ItemType Directory -Path $data -Force | Out-Null
    $process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $data 'http.stdout.log') -RedirectStandardError (Join-Path $data 'http.stderr.log') -PassThru
    Write-Output "Slacker MCP PID $($process.Id), http://127.0.0.1:$Port/mcp"
} else {
    & $python @arguments
}
