param([string]$Python = 'C:/Users/minhk/AppData/Local/Programs/Python/Python314/python.exe')
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$workspaceDirectory = Split-Path -Parent $projectDirectory
$clientDirectory = Join-Path $workspaceDirectory 'UC4NAutoCADMCPClient'
& "$projectDirectory/mcp_server/scripts/setup.ps1" -Python $Python
& "$clientDirectory/scripts/setup.ps1" -Python $Python
