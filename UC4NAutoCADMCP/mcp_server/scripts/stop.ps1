$componentDirectory = Split-Path -Parent $PSScriptRoot
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'python.exe' -and $_.CommandLine -like "*$componentDirectory*" -and $_.CommandLine -match 'run.py'
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Output "Stopped MCP server process $($_.ProcessId)"
}
