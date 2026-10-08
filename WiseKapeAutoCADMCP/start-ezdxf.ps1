$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'start-http.ps1'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script -Backend ezdxf
exit $LASTEXITCODE
