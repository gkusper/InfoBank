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
    $port = 8765

    $env:DATABASE_URL = "mysql+pymysql://infobank:infobank_dev_password@127.0.0.1:3307/infobank_db?charset=utf8mb4"
    $env:JWT_SECRET_KEY = "r1b-temporary-api-smoke-secret"
    $env:CHROMA_PERSIST_DIR = Join-Path ([System.IO.Path]::GetTempPath()) "infobank-r1b-api-smoke-chroma"
    $env:OPENAI_API_KEY = "r1b-placeholder-no-provider-calls"

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

    $databaseResult = Invoke-RestMethod "http://127.0.0.1:$port/api/test-db" -TimeoutSec 10
    $openApiStatus = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$port/openapi.json" -TimeoutSec 10).StatusCode
    if ($docsStatus -ne 200) { throw "/docs did not return HTTP 200" }
    if ($openApiStatus -ne 200) { throw "/openapi.json did not return HTTP 200" }
    if ($databaseResult.status -ne "success") { throw "/api/test-db did not report success" }

    Write-Output (
        "R1B_DOCKER_SMOKE=PASS mariadb=healthy test_db_status={0} users_in_db={1} docs_http={2} openapi_http={3} volume_deleted=false" -f `
        $databaseResult.status, $databaseResult.users_in_db, $docsStatus, $openApiStatus
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
