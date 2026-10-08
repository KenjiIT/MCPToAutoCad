param([ValidateSet('server','client')][string]$Component = 'client', [ValidateSet('com','ezdxf')][string]$Backend = 'com', [int]$Port = 0)
$projectDirectory = Split-Path -Parent $PSScriptRoot
$workspaceDirectory = Split-Path -Parent $projectDirectory
$clientDirectory = Join-Path $workspaceDirectory 'UC4NAutoCADMCPClient'
if ($Component -eq 'server') {
    if ($Port -eq 0) { $Port = 8768 }
    & "$projectDirectory/mcp_server/scripts/start.ps1" -Backend $Backend -Port $Port
} else {
    if ($Port -eq 0) { $Port = 8767 }
    & "$clientDirectory/scripts/start.ps1" -Port $Port
}
