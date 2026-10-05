$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Create .venv and install requirements first; see README.md.'
}
if (-not $env:AI_AUTOCAD_OPERATOR_TOKEN -or $env:AI_AUTOCAD_OPERATOR_TOKEN.Length -lt 32) {
    throw 'Set AI_AUTOCAD_OPERATOR_TOKEN to a random value of at least 32 characters.'
}
Set-Location -LiteralPath $projectRoot
& $pythonExe -m uvicorn ai_autocad.api:create_app --factory --host 127.0.0.1 --port 8765
