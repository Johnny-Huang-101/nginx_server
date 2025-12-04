# Path to the file you want to monitor
$watchFile = "D:\Exports\JSON\export-control.json"

# Path to the import script you want to run
$triggerScript = "D:\lims\code\lims\static\fa_export\Export-CaseData - Local.ps1"

$now = Get-Date

# Read watch file
if (-not (Test-Path $watchFile)) {
#    Write-Host "⚠️ Watch file not found. Export skipped."
    return
} else {
    $modified = (Get-Item $watchFile).LastWriteTime
        if (($now - $modified).TotalSeconds -lt 54) {
    #        Write-Host "✅ File modified in the last 54 seconds. Running trigger script: $triggerScript"
            &$triggerScript
    } else {
#        Write-Host "ℹ️ File has not been modified recently."
    }
}
