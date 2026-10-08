$componentDirectory = Split-Path -Parent $PSScriptRoot
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'python.exe' -and $_.CommandLine -like "*$componentDirectory*" -and $_.CommandLine -match 'uvicorn client.api:app'
} | ForEach-Object {
    # Include the client-owned Codex app-server / CLI processes.
    & taskkill.exe /PID $_.ProcessId /T /F 2>$null | Out-Null
    Write-Output "Stopped MCP client process tree $($_.ProcessId)"
}
