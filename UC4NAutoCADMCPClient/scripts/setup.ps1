param([string]$Python = 'C:/Users/minhk/AppData/Local/Programs/Python/Python314/python.exe')
$ErrorActionPreference = 'Stop'
$componentDirectory = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $componentDirectory
try {
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'venv failed.' }
    }
    $requirements = if (Test-Path -LiteralPath 'requirements.lock.txt') { 'requirements.lock.txt' } else { 'requirements.txt' }
    & ./.venv/Scripts/python.exe -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Installation failed.' }
} finally { Pop-Location }
