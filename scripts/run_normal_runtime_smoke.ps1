[CmdletBinding()]
param(
    [string]$PythonInterpreter = "backend_python/.venv_r1a/Scripts/python.exe",
    [string]$ExpectedDatabase = "infobank_db",
    [int]$Port = 8772,
    [switch]$ApplyMigration,
    [switch]$ConfirmUnexpectedDatabase,
    [switch]$UseExistingBackend
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonPath = if ([System.IO.Path]::IsPathRooted($PythonInterpreter)) {
    $PythonInterpreter
} else {
    Join-Path $repoRoot $PythonInterpreter
}
$artifactDir = Join-Path $repoRoot "artifacts\pre_push_runtime_audit\normal_runtime_smoke"
$schemaPath = Join-Path $artifactDir "schema_before.json"
$resultPath = Join-Path $artifactDir "endpoint_matrix.json"
$stdoutPath = Join-Path $artifactDir "backend.stdout.log"
$stderrPath = Join-Path $artifactDir "backend.stderr.log"
$backendProcess = $null
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Canonical Python interpreter is unavailable: $pythonPath"
}

Set-Location $repoRoot
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$schemaOutput = & $pythonPath scripts\check_database_schema.py --json 2>&1
$schemaExit = $LASTEXITCODE
$ErrorActionPreference = $previousPreference
$schemaText = ($schemaOutput -join "`n")
$schemaText | Set-Content -LiteralPath $schemaPath -Encoding utf8
$schema = $schemaText | ConvertFrom-Json
Write-Output ("NORMAL_RUNTIME_TARGET={0}" -f $schema.target)

if ($schema.database_name -ne $ExpectedDatabase -and -not $ConfirmUnexpectedDatabase) {
    throw "Refusing unexpected database name. Pass -ConfirmUnexpectedDatabase only after a verified backup."
}
if ($schemaExit -ne 0 -or $schema.status -ne "COMPATIBLE") {
    if (-not $ApplyMigration) {
        throw "Database schema is not compatible. Run the documented migration or pass -ApplyMigration explicitly."
    }
    & $pythonPath scripts\apply_database_migrations.py --expected-database $ExpectedDatabase --yes
    if ($LASTEXITCODE -ne 0) { throw "Explicit migration failed." }
}

$env:AI_PROVIDER = "deterministic-mock"
$env:OPENAI_API_KEY = ""
$baseUrl = "http://127.0.0.1:$Port"
try {
    if (-not $UseExistingBackend) {
        $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList "-m", "uvicorn", "main:app", "--app-dir", "backend_python", "--host", "127.0.0.1", "--port", "$Port" -WorkingDirectory $repoRoot -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru -WindowStyle Hidden
        $status = 0
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            if ($backendProcess.HasExited) { throw "Backend exited during startup." }
            try {
                $status = (Invoke-WebRequest -UseBasicParsing "$baseUrl/docs" -TimeoutSec 2).StatusCode
                if ($status -eq 200) { break }
            } catch {
                $status = 0
            }
            Start-Sleep -Seconds 1
        }
        if ($status -ne 200) { throw "Backend did not become ready." }
    }
    & $pythonPath scripts\run_normal_runtime_endpoints.py --base-url $baseUrl --output $resultPath
    if ($LASTEXITCODE -ne 0) { throw "Normal-runtime endpoint matrix failed." }
    Write-Output "NORMAL_RUNTIME_SMOKE=PASS"
    Write-Output ("RESULT={0}" -f $resultPath)
} finally {
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id
        $backendProcess.WaitForExit()
    }
}
