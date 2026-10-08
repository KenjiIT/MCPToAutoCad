$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    py -3 -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Slacker MCP virtual environment.' }
}
& $python -m pip install -e $root 'fastmcp>=3.4,<4'
if ($LASTEXITCODE -ne 0) { throw 'Could not install Slacker MCP and HTTP adapter dependencies.' }
Write-Output "Slacker AutoCAD MCP is ready: $python"
