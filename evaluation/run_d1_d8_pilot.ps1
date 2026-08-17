[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$MockGeneration,
    [switch]$RealApi,
    [switch]$DocumentOnly,
    [switch]$EvidenceOnly,
    [switch]$PreserveState,
    [string]$ResultsDir = "evaluation/results",
    [string]$DocumentFixture = "evaluation/fixtures/document_rag_v2.yaml",
    [string]$EvidenceBenchmark = "data/benchmarks/evidence_unit_v1",
    [int]$TopK = 4,
    [int]$Repetitions = 1,
    [string]$EnvFile = "backend_python/.env.eval",
    [string]$BaselineDiagnostic = ""
)

$ErrorActionPreference = "Stop"

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

$argsList = @("-m", "evaluation.run_d1_d8_pilot")
if ($CheckOnly) { $argsList += "--check-only" }
if ($MockGeneration) { $argsList += "--mock-generation" }
if ($RealApi) { $argsList += "--real-api" }
if ($DocumentOnly) { $argsList += "--document-only" }
if ($EvidenceOnly) { $argsList += "--evidence-only" }
if ($PreserveState) { $argsList += "--preserve-state" }
$argsList += @("--results-dir", $ResultsDir)
$argsList += @("--document-fixture", $DocumentFixture)
$argsList += @("--evidence-benchmark", $EvidenceBenchmark)
$argsList += @("--top-k", "$TopK")
$argsList += @("--repetitions", "$Repetitions")
$argsList += @("--env-file", $EnvFile)
if (-not [string]::IsNullOrWhiteSpace($BaselineDiagnostic)) {
    $argsList += @("--baseline-diagnostic", $BaselineDiagnostic)
}

& $python @argsList
exit $LASTEXITCODE
