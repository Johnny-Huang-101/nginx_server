# Expecting ~10k .csv files every month

$PruneLogPath = "D:\Exports\prune_log.txt"

function Log {
    param (
        [string]$Message
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $PruneLogPath -Value "$timestamp  $Message"
}

"`n----- Starting new prune run at $(Get-Date) -----`n" | Out-File $PruneLogPath -Append

# Log file path
$logPath = "D:\Exports\export-log.csv"

# Auto-prune logs and files older than 7 days
if (Test-Path $logPath) {
    $logData = Import-Csv -Path $logPath
    $cutoff = (Get-Date).AddDays(-7)

    # Split into keep vs. prune groups
    $entriesToKeep = @()
    $entriesToDelete = @()

    foreach ($entry in $logData) {
        $entryDate = $entry.Timestamp -as [datetime]
        if ($entryDate -and $entryDate -ge $cutoff) {
            $entriesToKeep += $entry
        }
        elseif ($entryDate) {
            $entriesToDelete += $entry
        }
    }
    if ($entriesToDelete) {
    }
    else {
        Log "Nothing to Delete."
    }

    Add-Type -AssemblyName Microsoft.VisualBasic

    foreach ($old in $entriesToDelete) {
        $fileToRecycle = $old.OutputFile
        if ($fileToRecycle -and (Test-Path $fileToRecycle)) {
            try {
                $shell = New-Object -ComObject Shell.Application
                $folder = Split-Path -Path $fileToRecycle
                $file = Get-Item $fileToRecycle
                $shell.Namespace($folder).ParseName($file.Name).InvokeVerb("delete")
                Log "Moved to Recycle Bin: $fileToRecycle"
            }
            catch {
                Log "Failed to recycle file: $fileToRecycle"
                Log "Error: $($_.Exception.Message)"
            }
        }
        else {
            Log "Error: $fileToRecycle not found."
        }
    }


    # Write back trimmed log
    $entriesToKeep | Export-Csv -Path $logPath -NoTypeInformation -Encoding UTF8
}
