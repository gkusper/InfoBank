[CmdletBinding()]
param(
    [string]$PythonInterpreter = "backend_python/.venv_r1a/Scripts/python.exe",
    [string]$OutputRoot = "artifacts/pre_freeze/operations-smoke",
    [string]$DatabaseHost = "127.0.0.1",
    [int]$DatabasePort = 3307,
    [string]$DatabaseUser = "infobank",
    [string]$DatabasePassword = $env:INFOBANK_SMOKE_DB_PASSWORD,
    [string]$AdminUser = "root",
    [string]$AdminPassword = $env:INFOBANK_SMOKE_ADMIN_PASSWORD,
    [string]$ContainerName = "infobank-mariadb"
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($DatabasePassword) -or [string]::IsNullOrWhiteSpace($AdminPassword)) {
    throw "Set INFOBANK_SMOKE_DB_PASSWORD and INFOBANK_SMOKE_ADMIN_PASSWORD for the isolated Docker smoke."
}
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonPath = if ([IO.Path]::IsPathRooted($PythonInterpreter)) { $PythonInterpreter } else { Join-Path $repoRoot $PythonInterpreter }
$output = if ([IO.Path]::IsPathRooted($OutputRoot)) { $OutputRoot } else { Join-Path $repoRoot $OutputRoot }
$sourceDb = "infobank_eval_prefreeze_ops_source"
$restoreDb = "infobank_eval_prefreeze_ops_restore"
$rollbackBaseDb = "infobank_eval_prefreeze_ops_rollback_base"
$rollbackRestoreDb = "infobank_eval_prefreeze_ops_rollback_restore"
$sourceUrl = "mysql+pymysql://${DatabaseUser}:${DatabasePassword}@${DatabaseHost}:${DatabasePort}/${sourceDb}"
$restoreUrl = "mysql+pymysql://${DatabaseUser}:${DatabasePassword}@${DatabaseHost}:${DatabasePort}/${restoreDb}"
$adminUrl = "mysql+pymysql://${AdminUser}:${AdminPassword}@${DatabaseHost}:${DatabasePort}/mysql"
$runtime = Join-Path $output "runtime"
$workflowOutput = Join-Path $output "api_workflow"
$sourceChroma = Join-Path $runtime "source_chroma"
$sourceStore = Join-Path $runtime "source_store"
$restoreChroma = Join-Path $runtime "restored_chroma"
$restoreStore = Join-Path $runtime "restored_source_store"
$backup = Join-Path $output "backup"
$backupChroma = Join-Path $backup "chroma"
$backupSourceStore = Join-Path $backup "source_store"
$dumpPath = Join-Path $backup "mariadb_logical.sql"
$rollbackDumpPath = Join-Path $backup "rollback_baseline.sql"

if (Test-Path -LiteralPath $output) { throw "Refusing to mix operations output: $output" }
New-Item -ItemType Directory -Force -Path $runtime,$backup | Out-Null
$docker = (Get-Command docker -ErrorAction Stop).Source

function Invoke-DockerChecked {
    param([string[]]$Arguments)
    & $docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed: docker $($Arguments -join ' ')" }
}

function Join-ProcessArguments {
    param([string[]]$Values)
    return (($Values | ForEach-Object { '"' + $_.Replace('"','\"') + '"' }) -join ' ')
}

function Get-StringSha256 {
    param([string]$Value)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value))).Replace('-','').ToLowerInvariant() }
    finally { $algorithm.Dispose() }
}

function Export-MariaDb {
    param([string]$Database, [string]$Destination)
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $docker
    $info.Arguments = Join-ProcessArguments @("exec",$ContainerName,"mariadb-dump","-u$AdminUser","-p$AdminPassword","--single-transaction","--routines","--events","$Database")
    $info.UseShellExecute = $false; $info.RedirectStandardOutput = $true; $info.RedirectStandardError = $true
    $process = [Diagnostics.Process]::Start($info)
    $stream = [IO.File]::Create($Destination)
    try { $process.StandardOutput.BaseStream.CopyTo($stream) } finally { $stream.Dispose() }
    $errorText = $process.StandardError.ReadToEnd(); $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw "mariadb-dump failed: $errorText" }
}

function Import-MariaDb {
    param([string]$Database, [string]$Source)
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $docker
    $info.Arguments = Join-ProcessArguments @("exec","-i",$ContainerName,"mariadb","-u$AdminUser","-p$AdminPassword",$Database)
    $info.UseShellExecute = $false; $info.RedirectStandardInput = $true; $info.RedirectStandardOutput = $true; $info.RedirectStandardError = $true
    $process = [Diagnostics.Process]::Start($info)
    $stream = [IO.File]::OpenRead($Source)
    try { $stream.CopyTo($process.StandardInput.BaseStream); $process.StandardInput.Close() } finally { $stream.Dispose() }
    $outputText = $process.StandardOutput.ReadToEnd(); $errorText = $process.StandardError.ReadToEnd(); $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw "MariaDB import failed: $errorText $outputText" }
}

Set-Location $repoRoot
& $pythonPath .\scripts\run_api_end_to_end_workflows.py --output $workflowOutput --database-url $sourceUrl --admin-database-url $adminUrl --chroma-dir $sourceChroma --source-storage-dir $sourceStore
if ($LASTEXITCODE -ne 0) { throw "API workflow failed" }

Export-MariaDb -Database $sourceDb -Destination $dumpPath
Copy-Item -LiteralPath $sourceChroma -Destination $backupChroma -Recurse
Copy-Item -LiteralPath $sourceStore -Destination $backupSourceStore -Recurse
Invoke-DockerChecked @("exec",$ContainerName,"mariadb","-u$AdminUser","-p$AdminPassword","-e","DROP DATABASE IF EXISTS ``$restoreDb``; CREATE DATABASE ``$restoreDb`` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON ``$restoreDb``.* TO '$DatabaseUser'@'%'; FLUSH PRIVILEGES;")
Import-MariaDb -Database $restoreDb -Source $dumpPath
Copy-Item -LiteralPath $backupChroma -Destination $restoreChroma -Recurse
Copy-Item -LiteralPath $backupSourceStore -Destination $restoreStore -Recurse
Copy-Item -LiteralPath (Join-Path $repoRoot "backend_python\config\controlled_failure_v3.json") -Destination $backup

& $pythonPath .\scripts\verify_pre_freeze_restore.py --source-database-url $sourceUrl --restored-database-url $restoreUrl --source-chroma $sourceChroma --restored-chroma $restoreChroma --source-store $sourceStore --restored-source-store $restoreStore --trace (Join-Path $workflowOutput "api_workflow_trace.jsonl") --output (Join-Path $output "restore_verification.json")
if ($LASTEXITCODE -ne 0) { throw "Restore verification failed" }

$baselineSql = Join-Path $runtime "rollback_baseline_schema.sql"
$baselineContent = (Get-Content -LiteralPath (Join-Path $repoRoot "infobank_db.sql") -Raw).Replace("infobank_db", $rollbackBaseDb)
[IO.File]::WriteAllText($baselineSql, $baselineContent, [Text.UTF8Encoding]::new($false))
Invoke-DockerChecked @("exec",$ContainerName,"mariadb","-u$AdminUser","-p$AdminPassword","-e","DROP DATABASE IF EXISTS ``$rollbackBaseDb``; DROP DATABASE IF EXISTS ``$rollbackRestoreDb``;")
Import-MariaDb -Database "mysql" -Source $baselineSql
Invoke-DockerChecked @("exec",$ContainerName,"mariadb","-u$AdminUser","-p$AdminPassword",$rollbackBaseDb,"-e","INSERT INTO users (id,email,username,password_hash) VALUES ('00000000-0000-0000-0000-000000000901','rollback@example.invalid','rollback-fixture','not-a-login-hash');")
Export-MariaDb -Database $rollbackBaseDb -Destination $rollbackDumpPath
Import-MariaDb -Database $rollbackBaseDb -Source (Join-Path $repoRoot "backend_python\migrations\citds_11_mysql.sql")
Import-MariaDb -Database $rollbackBaseDb -Source (Join-Path $repoRoot "backend_python\migrations\infocom_a_gate_phase1_mysql.sql")
Invoke-DockerChecked @("exec",$ContainerName,"mariadb","-u$AdminUser","-p$AdminPassword","-e","CREATE DATABASE ``$rollbackRestoreDb`` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
Import-MariaDb -Database $rollbackRestoreDb -Source $rollbackDumpPath
$rollbackRead = & $docker exec $ContainerName mariadb "-u$AdminUser" "-p$AdminPassword" $rollbackRestoreDb -N -e "SELECT username FROM users WHERE id='00000000-0000-0000-0000-000000000901';"
if ($LASTEXITCODE -ne 0 -or $rollbackRead.Trim() -ne "rollback-fixture") { throw "Backup-based rollback verification failed" }

& $pythonPath .\scripts\run_orphan_fixture_smoke.py --output (Join-Path $output "orphan_fixture_report.json")
if ($LASTEXITCODE -ne 0) { throw "Orphan fixture smoke failed" }

$files = Get-ChildItem -LiteralPath $backup -File -Recurse | Sort-Object FullName | ForEach-Object { [ordered]@{ name=$_.FullName.Substring($backup.Length).TrimStart('\').Replace('\','/'); sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant(); byte_size=$_.Length } }
$manifest = [ordered]@{
    schema_version = "infobank-pre-freeze-backup-v1"
    status = "PASS"
    exact_commit = (git rev-parse HEAD).Trim()
    database_names = [ordered]@{ source=$sourceDb; restored=$restoreDb; rollback_baseline=$rollbackBaseDb; rollback_restored=$rollbackRestoreDb }
    scopes = @("MariaDB logical schema/data","Chroma persist directory","durable PDF source store","controlled-failure non-secret config","commit/config hashes")
    excluded = @(".env","secrets","Gmail tokens","private user data")
    files = $files
    backup_file_manifest_sha256 = Get-StringSha256 ($files | ConvertTo-Json -Depth 4)
    source_store_file_count = @(Get-ChildItem -LiteralPath $sourceStore -File -Recurse).Count
    rollback_type = "BACKUP_BASED_NOT_REVERSE_MIGRATION"
    network_provider_called = $false
    production_data_touched = $false
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output "backup_manifest.json") -Encoding utf8
Write-Output "PRE_FREEZE_OPERATIONS_SMOKE=PASS"
Write-Output "OUTPUT=$output"
