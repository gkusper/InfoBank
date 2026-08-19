[CmdletBinding()]
param(
    [Alias("Python")]
    [string]$PythonInterpreter = "backend_python/.venv_r1a/Scripts/python.exe",
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"
$startedAt = Get-Date
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonPath = if ([System.IO.Path]::IsPathRooted($PythonInterpreter)) {
    $PythonInterpreter
} else {
    Join-Path $repoRoot $PythonInterpreter
}
$artifactDir = Join-Path $repoRoot "artifacts\local_quality_gate"
$summaryPath = Join-Path $artifactDir "latest.json"
$junitPath = Join-Path $artifactDir "latest.junit.xml"
$steps = [ordered]@{}
$blockingFailure = $false

New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Python interpreter not found: $pythonPath"
}

function Invoke-PythonStep {
    param(
        [string]$Name,
        [string[]]$CommandArgs
    )
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & $pythonPath @CommandArgs 2>&1
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    $timer.Stop()
    foreach ($line in $output) { Write-Output $line.ToString() }
    $script:steps[$Name] = [ordered]@{
        status = if ($exitCode -eq 0) { "PASS" } else { "FAIL" }
        exit_code = $exitCode
        elapsed_seconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
        command = "$pythonPath $($CommandArgs -join ' ')"
    }
    if ($exitCode -ne 0) { $script:blockingFailure = $true }
}

Set-Location $repoRoot
$head = (git rev-parse HEAD).Trim()
$branch = (git branch --show-current).Trim()

Invoke-PythonStep "pip_check" @("-m", "pip", "check")
Invoke-PythonStep "compileall" @(
    "-m", "compileall", "-q", "-x", "[\\/](?:\.venv[^\\/]*|venv)[\\/]", "backend_python", "evaluation"
)
Invoke-PythonStep "pytest" @(
    "-m", "pytest", "backend_python/tests", "evaluation/tests", "-q", "--junitxml=$junitPath"
)

$env:DATABASE_URL = "sqlite+pysqlite:///:memory:"
$env:JWT_SECRET_KEY = "r1b-local-quality-gate-secret"
$env:CHROMA_PERSIST_DIR = Join-Path ([System.IO.Path]::GetTempPath()) "infobank-r1b-quality-gate-chroma"
$importCode = @'
import os
import sys
from unittest.mock import patch
sys.path.insert(0, 'backend_python')
os.environ.pop('OPENAI_API_KEY', None)
with patch('dotenv.load_dotenv', return_value=False):
    import ai_service, evidence_service, routers.evidence
print('R1B_IMPORT_OK')
'@
Invoke-PythonStep "import_smoke" @("-c", $importCode)

$dockerStatus = "PENDING"
if ($SkipDocker) {
    $steps["docker_api_smoke"] = [ordered]@{
        status = "PENDING"
        exit_code = 0
        elapsed_seconds = 0
        command = "scripts/run_api_smoke.ps1 (skipped by -SkipDocker)"
        warning = "Docker/API smoke explicitly skipped"
    }
} else {
    $dockerTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $shellPath = (Get-Process -Id $PID).Path
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $smokeOutput = & $shellPath -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "run_api_smoke.ps1") -PythonInterpreter $pythonPath 2>&1
    $smokeExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    $dockerTimer.Stop()
    foreach ($line in $smokeOutput) { Write-Output $line.ToString() }
    if ($smokeOutput -match "R1B_DOCKER_SMOKE=PASS") {
        $dockerStatus = "PASS"
    } elseif ($smokeOutput -match "R1B_DOCKER_SMOKE=PENDING") {
        $dockerStatus = "PENDING"
    } else {
        $dockerStatus = "FAIL"
        $blockingFailure = $true
    }
    if ($smokeExitCode -ne 0) { $blockingFailure = $true }
    $steps["docker_api_smoke"] = [ordered]@{
        status = $dockerStatus
        exit_code = $smokeExitCode
        elapsed_seconds = [Math]::Round($dockerTimer.Elapsed.TotalSeconds, 3)
        command = "scripts/run_api_smoke.ps1 -PythonInterpreter $pythonPath"
        output = ($smokeOutput -join "`n")
    }
}

$testCounts = [ordered]@{ passed = 0; failed = 0; skipped = 0; total = 0 }
if (Test-Path -LiteralPath $junitPath) {
    [xml]$junit = Get-Content -LiteralPath $junitPath -Raw
    $suite = $junit.SelectSingleNode("//testsuite")
    if ($suite) {
        $testCounts.total = [int]$suite.tests
        $testCounts.failed = [int]$suite.failures + [int]$suite.errors
        $testCounts.skipped = [int]$suite.skipped
        $testCounts.passed = $testCounts.total - $testCounts.failed - $testCounts.skipped
    }
}

$finishedAt = Get-Date
$overall = if ($blockingFailure) {
    "FAIL"
} elseif ($dockerStatus -eq "PENDING") {
    "PASS_WITH_PENDING_DOCKER_SMOKE"
} else {
    "PASS"
}
$summary = [ordered]@{
    schema_version = "r1b-local-quality-gate-v1"
    status = $overall
    branch = $branch
    commit_sha = $head
    started_at = $startedAt.ToUniversalTime().ToString("o")
    finished_at = $finishedAt.ToUniversalTime().ToString("o")
    elapsed_seconds = [Math]::Round(($finishedAt - $startedAt).TotalSeconds, 3)
    tests = $testCounts
    steps = $steps
    warnings = @(
        "Chroma may emit known non-blocking telemetry warnings during import"
    )
}
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding utf8

Write-Output ("R1B QUALITY GATE: {0}" -f $overall)
Write-Output ("COMMIT: {0}" -f $head)
Write-Output ("TESTS: passed={0} failed={1} skipped={2} total={3}" -f $testCounts.passed, $testCounts.failed, $testCounts.skipped, $testCounts.total)
foreach ($name in $steps.Keys) {
    Write-Output ("{0}: {1}" -f $name, $steps[$name].status)
}
Write-Output ("SUMMARY: {0}" -f $summaryPath)

if ($blockingFailure) { exit 1 }
exit 0
