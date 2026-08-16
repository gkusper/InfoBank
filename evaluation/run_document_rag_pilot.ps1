[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$MockGeneration,
    [string]$ResultsDir = "evaluation/results",
    [int]$TopK = 4,
    [int]$Repetitions = 1,
    [string]$CaseIds = "FULL_01,METADATA_01,DENY_01,AGG_SAFE_01,AGG_INDIVIDUAL_01,MIXED_PRIMARY_01,CONTEXT_ONLY_01",
    [string]$EnvFile = "backend_python/.env.eval"
)

$ErrorActionPreference = "Stop"

$modeCount = 0
if ($CheckOnly) { $modeCount += 1 }
if ($MockGeneration) { $modeCount += 1 }
if ($modeCount -gt 1) {
    Write-Error "Use only one of -CheckOnly or -MockGeneration."
    exit 2
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

$python = Join-Path $repoRoot "backend_python/.venv_eval/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "Evaluation Python not found: $python"
    exit 2
}

$envPath = Join-Path $repoRoot $EnvFile
if (-not (Test-Path -LiteralPath $envPath)) {
    Write-Error "Evaluation env file not found: $envPath. Create backend_python/.env.eval with DATABASE_URL for infobank_eval and CHROMA_PERSIST_DIR=./chroma_eval. Do not put OPENAI_API_KEY in this file."
    exit 2
}

if (-not $CheckOnly -and -not $MockGeneration) {
    if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
        Write-Error "PILOT BLOCKED: OPENAI_API_KEY NOT CONFIGURED"
        exit 2
    }
    Write-Host "OPENAI_API_KEY visible: YES"
}

if ($CheckOnly) {
    $mode = "--check-only"
} elseif ($MockGeneration) {
    $mode = "--mock-generation"
} else {
    $mode = "--real-api"
}

& $python -m evaluation.run_document_rag_pilot `
    $mode `
    --results-dir $ResultsDir `
    --top-k $TopK `
    --repetitions $Repetitions `
    --case-ids $CaseIds `
    --env-file $EnvFile

exit $LASTEXITCODE
