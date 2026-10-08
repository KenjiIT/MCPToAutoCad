param([int]$Port = 8771, [switch]$Background)
$ErrorActionPreference = 'Stop'
$componentDirectory = Split-Path -Parent $PSScriptRoot
$python = Join-Path $componentDirectory '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run this component setup.ps1 first.' }
if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) { throw "Port $Port already in use." }
$env:PYTHONUTF8 = '1'
$processArguments = @('-m','uvicorn','client.api:app','--host','127.0.0.1','--port',"$Port")
if ($Background) {
    $dataDirectory = Join-Path $componentDirectory 'data'
    New-Item -ItemType Directory -Path $dataDirectory -Force | Out-Null
    $process = Start-Process -FilePath $python -ArgumentList $processArguments -WorkingDirectory $componentDirectory -WindowStyle Hidden -RedirectStandardOutput "$dataDirectory/client.stdout.log" -RedirectStandardError "$dataDirectory/client.stderr.log" -PassThru
    Write-Output "MCP client PID $($process.Id), http://127.0.0.1:$Port"
} else {
    Push-Location -LiteralPath $componentDirectory
    try { & $python @processArguments } finally { Pop-Location }
}
