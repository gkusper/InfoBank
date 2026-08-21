[CmdletBinding()]
param(
    [string]$PythonInterpreter = "backend_python/.venv_r1a/Scripts/python.exe"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonPath = if ([System.IO.Path]::IsPathRooted($PythonInterpreter)) {
    $PythonInterpreter
} else {
    Join-Path $repoRoot $PythonInterpreter
}
$apiProcess = $null
$originalLocation = Get-Location

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    Write-Output "R1B_DOCKER_SMOKE=FAIL reason=python_interpreter_missing"
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Output "R1B_DOCKER_SMOKE=PENDING reason=docker_cli_unavailable"
    exit 0
}

try {
    Set-Location $repoRoot
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    docker info *> $null
    $dockerInfoExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    if ($dockerInfoExitCode -ne 0) {
        Write-Output "R1B_DOCKER_SMOKE=PENDING reason=docker_daemon_unavailable"
        exit 0
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    docker compose up -d db
    $composeExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    if ($composeExitCode -ne 0) {
        throw "docker compose up -d db failed"
    }

    $health = ""
    for ($attempt = 0; $attempt -lt 24; $attempt++) {
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $health = (docker inspect --format '{{.State.Health.Status}}' infobank-mariadb 2>$null).Trim()
        $inspectExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorActionPreference
        if ($inspectExitCode -ne 0) { throw "Unable to inspect MariaDB health" }
        if ($health -eq "healthy") { break }
        if ($health -eq "unhealthy") { throw "MariaDB reported unhealthy" }
        Start-Sleep -Seconds 5
    }
    if ($health -ne "healthy") {
        throw "MariaDB did not become healthy within 120 seconds"
    }

    $artifactDir = Join-Path $repoRoot "artifacts\local_quality_gate"
    New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
    $stdoutLog = Join-Path $artifactDir "api-smoke.stdout.log"
    $stderrLog = Join-Path $artifactDir "api-smoke.stderr.log"
    $backendDir = Join-Path $repoRoot "backend_python"
    # Keep the smoke API away from the documented local frontend port (8765)
    # so a developer can leave the static UI running during this isolated gate.
    $port = 18765

    $env:DATABASE_URL = "mysql+pymysql://infobank:infobank_dev_password@127.0.0.1:3307/infobank_db?charset=utf8mb4"
    $env:JWT_SECRET_KEY = "r1b-temporary-api-smoke-secret"
    $env:AI_PROVIDER = "deterministic-mock"
    $env:CHROMA_PERSIST_DIR = Join-Path ([System.IO.Path]::GetTempPath()) "infobank-r1b-api-smoke-chroma"
    $env:SOURCE_STORAGE_DIR = Join-Path ([System.IO.Path]::GetTempPath()) "infobank-r1b-api-smoke-source"
    $env:OPENAI_API_KEY = ""
    $env:INFOBANK_MIGRATION_SMOKE_ADMIN_DATABASE_URL = "mysql+pymysql://root:infobank_root_password@127.0.0.1:3307/mysql?charset=utf8mb4"

    & $pythonPath (Join-Path $PSScriptRoot "check_database_schema.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Docker database schema is incompatible; the gate will not mutate it automatically"
    }
    & $pythonPath (Join-Path $PSScriptRoot "run_database_migration_smoke.py") --output (Join-Path $artifactDir "legacy-migration-smoke.json")
    if ($LASTEXITCODE -ne 0) {
        throw "Isolated legacy database migration smoke failed"
    }
    & $pythonPath (Join-Path $PSScriptRoot "run_clean_database_migration_smoke.py") --output (Join-Path $artifactDir "clean-migration-smoke.json")
    if ($LASTEXITCODE -ne 0) {
        throw "Isolated clean database migration smoke failed"
    }

    $apiProcess = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$port" `
        -WorkingDirectory $backendDir `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -PassThru `
        -WindowStyle Hidden

    $docsStatus = 0
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($apiProcess.HasExited) {
            throw "FastAPI exited before the smoke endpoints became available"
        }
        try {
            $docsStatus = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$port/docs" -TimeoutSec 3).StatusCode
        } catch {
            $docsStatus = 0
        }
        if ($docsStatus -eq 200) { break }
        Start-Sleep -Seconds 2
    }

    $smokeEmail = "r1b-api-smoke@example.invalid"
    $smokePassword = "R1b-local-api-smoke-password-2026!"
    $registrationBody = @{
        email = $smokeEmail
        username = "r1b-api-smoke"
        password = $smokePassword
    } | ConvertTo-Json
    try {
        Invoke-RestMethod `
            -Method Post `
            -Uri "http://127.0.0.1:$port/api/register" `
            -ContentType "application/json" `
            -Body $registrationBody `
            -TimeoutSec 10 | Out-Null
    } catch {
        # A persistent local smoke database may already contain this
        # task-owned account. Authentication below remains the authority.
    }
    $loginBody = @{
        email = $smokeEmail
        password = $smokePassword
    } | ConvertTo-Json
    $loginResult = Invoke-RestMethod `
        -Method Post `
        -Uri "http://127.0.0.1:$port/api/login" `
        -ContentType "application/json" `
        -Body $loginBody `
        -TimeoutSec 10
    if (-not $loginResult.access_token) { throw "Smoke authentication did not return an access token" }
    $authHeaders = @{ Authorization = "Bearer $($loginResult.access_token)" }
    $databaseResult = Invoke-RestMethod "http://127.0.0.1:$port/api/test-db" -Headers $authHeaders -TimeoutSec 10
    $schemaResult = Invoke-RestMethod "http://127.0.0.1:$port/api/health/schema" -TimeoutSec 10
    $openApiStatus = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$port/openapi.json" -TimeoutSec 10).StatusCode
    if ($docsStatus -ne 200) { throw "/docs did not return HTTP 200" }
    if ($openApiStatus -ne 200) { throw "/openapi.json did not return HTTP 200" }
    if ($databaseResult.status -ne "success") { throw "/api/test-db did not report success" }
    if (-not $schemaResult.schema.compatible) { throw "/api/health/schema did not report compatibility" }

    Write-Output (
        "R1B_DOCKER_SMOKE=PASS mariadb=healthy authenticated_test_db_status={0} docs_http={1} openapi_http={2} schema_compatible=true legacy_migration=pass clean_migration=pass volume_deleted=false" -f `
        $databaseResult.status, $docsStatus, $openApiStatus
    )
    exit 0
} catch {
    Write-Output ("R1B_DOCKER_SMOKE=FAIL reason={0}" -f ($_.Exception.Message -replace '\s+', '_'))
    exit 1
} finally {
    if ($apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id
        $apiProcess.WaitForExit()
    }
    Set-Location $originalLocation
}
