param([ValidateSet('all','server','client')][string]$Component = 'all', [ValidateSet('com','ezdxf')][string]$Backend = 'com', [int]$ServerPort = 8768, [int]$Port = 8767)
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$workspaceDirectory = Split-Path -Parent $projectDirectory
$clientDirectory = Join-Path $workspaceDirectory 'UC4NAutoCADMCPClient'
if ($Component -in @('all','server')) { & "$projectDirectory/mcp_server/scripts/start.ps1" -Backend $Backend -Port $ServerPort -Background }
if ($Component -in @('all','client')) { & "$clientDirectory/scripts/start.ps1" -Port $Port -Background }
