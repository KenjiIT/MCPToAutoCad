$acadExe = 'C:/Program Files/Autodesk/AutoCAD 2027/acad.exe'
$manifest = 'C:/Program Files/Autodesk/ApplicationPlugins/AutoCAD-MCP-Server-2027.bundle/PackageContents.xml'
$acadProcesses = @(Get-Process acad -ErrorAction SilentlyContinue)
$comProbe = [ordered]@{ connected = $false; version = $null; documents = $null; error = $null }
$acadApp = $null
if ($acadProcesses.Count -gt 0) {
    try {
        $acadApp = [Runtime.InteropServices.Marshal]::GetActiveObject('AutoCAD.Application.26')
        $comProbe.connected = ($null -ne $acadApp)
        $comProbe.version = $acadApp.Version
        $comProbe.documents = $acadApp.Documents.Count
    } catch {
        $comProbe.error = $_.Exception.Message
    } finally {
        if ($null -ne $acadApp) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($acadApp) }
    }
}
[ordered]@{
    checkedAt = (Get-Date -Format o)
    autoCadInstalled = (Test-Path -LiteralPath $acadExe)
    autoCadProcesses = @($acadProcesses | Select-Object Id, Path)
    autodeskMcpPluginInstalled = (Test-Path -LiteralPath $manifest)
    comRegistered = (Test-Path -LiteralPath 'Registry::HKEY_CLASSES_ROOT\AutoCAD.Application.26')
    readOnlyComProbe = $comProbe
    externalMcpWriteVerified = $false
    note = 'Installation is not proof of external MCP connectivity or write capability.'
} | ConvertTo-Json -Depth 4
