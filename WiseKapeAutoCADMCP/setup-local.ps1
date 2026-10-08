$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    py -3.14 -m venv (Join-Path $projectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the project virtual environment.' }
}

# Keep the MCP SDK at the version pinned by the upstream uv.lock.
& $python -m pip install -e $projectRoot 'mcp==1.29.0'
if ($LASTEXITCODE -ne 0) { throw 'Could not install WiseKape AutoCAD MCP dependencies.' }

Write-Output "WiseKape AutoCAD MCP is ready: $python"
