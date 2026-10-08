param([ValidateSet('all','server','client')][string]$Component = 'all')
$projectDirectory = Split-Path -Parent $PSScriptRoot
$workspaceDirectory = Split-Path -Parent $projectDirectory
$clientDirectory = Join-Path $workspaceDirectory 'UC4NAutoCADMCPClient'
if ($Component -in @('all','client')) { & "$clientDirectory/scripts/stop.ps1" }
if ($Component -in @('all','server')) { & "$projectDirectory/mcp_server/scripts/stop.ps1" }
