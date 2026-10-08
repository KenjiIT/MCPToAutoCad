$root = [regex]::Escape($PSScriptRoot)
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'python.exe' -and $_.CommandLine -match $root -and $_.CommandLine -match 'http_host.py'
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Output "Stopped Slacker MCP process $($_.ProcessId)"
}
