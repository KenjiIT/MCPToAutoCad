param([string]$Python = 'C:/Users/minhk/AppData/Local/Programs/Python/Python314/python.exe')
$ErrorActionPreference = 'Stop'
$componentDirectory = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $componentDirectory
try {
    if (-not (Test-Path -LiteralPath 'upstream')) {
        git clone https://github.com/U-C4N/Autocad-MCP.git upstream
        if ($LASTEXITCODE -ne 0) { throw 'Clone failed.' }
        git -C upstream checkout cdb10638963898b3ea9b10cdd96a2c9bc495f184
        if ($LASTEXITCODE -ne 0) { throw 'Checkout failed.' }
    }
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'venv failed.' }
    }
    $requirements = if (Test-Path -LiteralPath 'requirements.lock.txt') { 'requirements.lock.txt' } else { 'requirements.txt' }
    & ./.venv/Scripts/python.exe -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Installation failed.' }
} finally { Pop-Location }
