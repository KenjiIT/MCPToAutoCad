param([ValidateSet('ezdxf','com','file_ipc')][string]$Backend = 'ezdxf', [int]$Port = 8769, [switch]$Background)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run .\setup-local.ps1 first.' }
if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) { throw "Port $Port is already in use." }

$scriptPath = Join-Path $projectRoot 'run-http.py'
if ($Background) {
    $logs = Join-Path $projectRoot 'data\server'
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    $arguments = @('-u', ('"{0}"' -f $scriptPath), '--backend', $Backend, '--port', "$Port")
    $process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'stdout.log') -RedirectStandardError (Join-Path $logs 'stderr.log') -PassThru
    $deadline = (Get-Date).AddSeconds(15)
    $listener = $null
    do {
        Start-Sleep -Milliseconds 250
        $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    } while (-not $listener -and (Get-Date) -lt $deadline -and -not $process.HasExited)
    if (-not $listener) {
        if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
        Get-Content (Join-Path $logs 'stderr.log') -Tail 30 -ErrorAction SilentlyContinue
        throw "WiseKape MCP did not listen on port $Port."
    }
    Write-Output "WiseKape MCP listening PID $($listener.OwningProcess) (launcher PID $($process.Id)); http://127.0.0.1:$Port/mcp"
} else {
    & $python -u $scriptPath --backend $Backend --port $Port
}
