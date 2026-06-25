param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$BackupDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $BackupDir "..\..")

$Items = @(
    @{
        Source = Join-Path $BackupDir "data\xsi.db"
        Target = Join-Path $ProjectRoot "data\xsi.db"
    },
    @{
        Source = Join-Path $BackupDir "data\xsi.db-wal"
        Target = Join-Path $ProjectRoot "data\xsi.db-wal"
        Optional = $true
    },
    @{
        Source = Join-Path $BackupDir "data\xsi.db-shm"
        Target = Join-Path $ProjectRoot "data\xsi.db-shm"
        Optional = $true
    },
    @{
        Source = Join-Path $BackupDir "config\config.yaml"
        Target = Join-Path $ProjectRoot "config.yaml"
    }
)

Write-Host "XSI Phase 2 rollback helper"
Write-Host "Backup:  $BackupDir"
Write-Host "Project: $ProjectRoot"

foreach ($Item in $Items) {
    if (-not (Test-Path -LiteralPath $Item.Source)) {
        if ($Item.Optional) {
            Write-Host "SKIP optional missing source: $($Item.Source)"
            continue
        }
        throw "Missing required backup source: $($Item.Source)"
    }

    Write-Host "RESTORE $($Item.Source) -> $($Item.Target)"

    if ($Apply) {
        $TargetDir = Split-Path -Parent $Item.Target
        New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
        Copy-Item -LiteralPath $Item.Source -Destination $Item.Target -Force
    }
}

if ($Apply) {
    Write-Host "Rollback restore completed."
} else {
    Write-Host "Dry run only. Re-run with -Apply to restore files."
}
