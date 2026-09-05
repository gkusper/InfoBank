[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$BuildBenchmarks,
    [switch]$ValidateBenchmarks,
    [switch]$DocumentOnly,
    [switch]$EvidenceOnly,
    [switch]$RealApi,
    [switch]$MockGeneration,
    [switch]$Resume,
    [switch]$ScoreOnly,
    [switch]$ReportOnly,
    [string]$ResultsDir = "evaluation/results",
    [string]$DocumentFixture = "evaluation/fixtures/document_rag_v3.yaml",
    [string]$EvidenceBenchmark = "data/benchmarks/evidence_unit_v2_holdout",
    [string]$PublicationDir = "evaluation/publication_results/d1_d8_large_scale_v1",
    [string]$EnvFile = "backend_python/.env.eval",
    [int]$TopK = 4,
    [int]$DocumentRepetitions = 5,
    [int]$EvidenceRepetitions = 3,
    [int]$BootstrapSamples = 10000
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

$argsList = @("-m", "evaluation.run_d1_d8_large_scale")
if ($CheckOnly) { $argsList += "--check-only" }
if ($BuildBenchmarks) { $argsList += "--build-benchmarks" }
if ($ValidateBenchmarks) { $argsList += "--validate-benchmarks" }
if ($DocumentOnly) { $argsList += "--document-only" }
if ($EvidenceOnly) { $argsList += "--evidence-only" }
if ($RealApi) { $argsList += "--real-api" }
if ($MockGeneration) { $argsList += "--mock-generation" }
if ($Resume) { $argsList += "--resume" }
if ($ScoreOnly) { $argsList += "--score-only" }
if ($ReportOnly) { $argsList += "--report-only" }
$argsList += @("--results-dir", $ResultsDir)
$argsList += @("--document-fixture", $DocumentFixture)
$argsList += @("--evidence-benchmark", $EvidenceBenchmark)
$argsList += @("--publication-dir", $PublicationDir)
$argsList += @("--env-file", $EnvFile)
$argsList += @("--top-k", "$TopK")
$argsList += @("--document-repetitions", "$DocumentRepetitions")
$argsList += @("--evidence-repetitions", "$EvidenceRepetitions")
$argsList += @("--bootstrap-samples", "$BootstrapSamples")

& $python @argsList
exit $LASTEXITCODE
