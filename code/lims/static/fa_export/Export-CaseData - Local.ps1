param (
    [string]$controlPath = "D:\Exports\JSON\export-control.json"
)

# Parameters
$server = "OCME-LIMS"
$database = "lims"

$timestamp = Get-Date -Format "yyyyMMdd_HHmm"

$now = Get-Date

# Read control file
if (-not (Test-Path $controlPath)) {
#    Write-Host "⚠️ Control file not found. Export skipped."
    return
}

$control = Get-Content $controlPath | ConvertFrom-Json
#$now = Get-Date
$type = $control.type
$prefix = $control.initials
$shouldRun = $false

# Delay/runNow logic
if ($control.runNow -eq $true) {
    $shouldRun = $true
    $control.runNow = $false
} elseif ($now -ge [datetime]$control.delayUntil) {
    $shouldRun = $true
}

if (-not $shouldRun) {
#    Write-Host "⏸ Export skipped due to delay or scheduling control."
    return
}

switch ($type) {
    "1d_15m" {
        $startDate = $now.AddDays(-1).ToString("yyyy-MM-dd")
        $endDate   = $now.ToString("yyyy-MM-dd")
    }
    "7d_1h" {
        $startDate = $now.AddDays(-8).ToString("yyyy-MM-dd")  # 7 days, minus most recent 1
        $endDate   = $now.AddDays(-1).ToString("yyyy-MM-dd")
    }
    "30d_13h" {
        $startDate = $now.AddDays(-37).ToString("yyyy-MM-dd")  # 30 days, minus most recent 7
        $endDate   = $now.AddDays(-7).ToString("yyyy-MM-dd")
    }
    "365d_24h_a" {
        $startDate = $now.AddMonths(-12).ToString("yyyy-MM-dd")
        $endDate   = $now.AddMonths(-6).AddDays(-1).ToString("yyyy-MM-dd")
    }
    "365d_24h_b" {
        $startDate = $now.AddMonths(-6).ToString("yyyy-MM-dd")
        $endDate   = $now.ToString("yyyy-MM-dd")
    }
    default {
        # Fallback: use explicit dates from JSON (e.g., ad-hoc)
        $startDate = $control.startDate
        $endDate   = $control.endDate
    }
}

# Log file path
$logPath = "D:\Exports\export-log.csv"

# Compose SQL query that calls your stored procedure
$query = @"
EXEC dbo.usp_Export_CaseData 
    @StartDate = '$startDate', 
    @EndDate = '$endDate'
"@

# Output file path with timestamp, start and end for the filename (yyMMdd)
$startTag = (Get-Date $startDate).ToString("yyMMdd")
$endTag = (Get-Date $endDate).ToString("yyMMdd")
$outputFileName = "${prefix}export_${timestamp}_${startTag}-${endTag}.csv"
$outputPath = "D:\Exports\$outputFileName"

# Try to run export and log success/failure
try {
    Invoke-Sqlcmd -ServerInstance $server -Database $database -Query $query -QueryTimeout 600 -ConnectionTimeout 60|
        Export-Csv -Path $outputPath -NoTypeInformation -Encoding UTF8

#    Write-Host "controlPath: $controlPath"
#    Write-Host "✅ Export complete: $outputPath"
    
    # Update lastRun in control file
    $control.lastRun = $now.ToString("s")
    Set-Content -Path $controlPath -Value ($control | ConvertTo-Json -Depth 10)

    # Append success to log
    $logEntry = [PSCustomObject]@{
        Timestamp     = $now.ToString("s")
        Status        = "Success"
        Type          = $control.type  # e.g., "5min", "hourly", etc.
        StartDate     = $startDate
        EndDate       = $endDate
        OutputFile    = $outputPath
        ErrorMessage  = ""
        LIMS_Imported = ""
        LIMS_Error    = ""
        LIMS_Completed = ""
    }
    $logExists = Test-Path $logPath
    $logEntry | Export-Csv -Path $logPath -Append -NoTypeInformation -Encoding UTF8
    if (-not $logExists) {
        # Add header if new log file was just created
        $logHeader = $logEntry | Select-Object *
        $logHeader | Export-Csv -Path $logPath -NoTypeInformation -Encoding UTF8
    }
}
catch {
#    Write-Host "controlPath: $controlPath"
#    Write-Host "❌ Export failed: $_"
    $logEntry = [PSCustomObject]@{
        Timestamp     = $now.ToString("s")
        Status        = "Fail"
        Type          = $control.type  # e.g., "5min", "hourly", etc.
        StartDate     = $startDate
        EndDate       = $endDate
        OutputFile    = $outputPath
        ErrorMessage  = ""
        LIMS_Imported = ""
        LIMS_Error    = ""
        LIMS_Completed = ""
    }
    $logEntry | Export-Csv -Path $logPath -Append -NoTypeInformation -Encoding UTF8
}

