[CmdletBinding()]
param(
    [switch]$SkipDocker,
    [switch]$SkipPackageInstall,
    [switch]$PrepareEvalDatabase,
    [switch]$ResetEvaluationState,
    [switch]$RunUnitTests,
    [switch]$RunPilotCheck,
    [switch]$ForceEnvFiles,
    [string]$PipCacheDir = ".pip-cache"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "== $Message =="
}

function Get-FirstCommand {
    param([string]$Name)
    Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
}

function Get-ComposeDbEnvironment {
    param([string]$ComposePath)

    $content = Get-Content $ComposePath -Raw
    $result = @{}
    foreach ($key in @("MARIADB_DATABASE", "MARIADB_USER", "MARIADB_PASSWORD", "MARIADB_ROOT_PASSWORD")) {
        if ($content -match "(?m)^\s+${key}:\s*(.+?)\s*$") {
            $result[$key] = $Matches[1].Trim().Trim("'").Trim('"')
        }
    }

    foreach ($key in @("MARIADB_USER", "MARIADB_PASSWORD", "MARIADB_ROOT_PASSWORD")) {
        if (-not $result.ContainsKey($key)) {
            throw "Could not read $key from docker-compose.yml."
        }
    }

    return $result
}

function Test-Python312Candidate {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    $commandInfo = Get-FirstCommand $Command
    if (-not $commandInfo) {
        return $null
    }

    try {
        $version = & $Command @Arguments -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $null
        }
        if ($version -match "^3\.12\.") {
            return @{
                Command = $Command
                Arguments = $Arguments
                Version = $version.Trim()
            }
        }
    } catch {
        return $null
    }

    return $null
}

function Find-Python312 {
    $candidates = @(
        @{ Command = "py"; Arguments = @("-3.12") },
        @{ Command = "python"; Arguments = @() },
        @{ Command = "python3"; Arguments = @() }
    )

    foreach ($candidate in $candidates) {
        $match = Test-Python312Candidate -Command $candidate.Command -Arguments $candidate.Arguments
        if ($match) {
            return $match
        }
    }

    throw "Python 3.12 was not found. Install Python 3.12 or make python/py available in this PowerShell session."
}

function Test-LocalPort {
    param([int]$Port)
    return [bool](Test-NetConnection 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue)
}

function Initialize-EvaluationDatabase {
    param(
        [string]$Python,
        [string]$RootPassword,
        [bool]$Reset
    )

    $env:INFOBANK_REPRO_ROOT_PASSWORD = $RootPassword
    try {
        $resetValue = if ($Reset) { "1" } else { "0" }
        $script = @'
import os
import pathlib
import pymysql

root = pathlib.Path.cwd()
password = os.environ["INFOBANK_REPRO_ROOT_PASSWORD"]
reset = os.environ.get("INFOBANK_REPRO_RESET") == "1"

connection = pymysql.connect(
    host="127.0.0.1",
    port=3307,
    user="root",
    password=password,
    charset="utf8mb4",
    autocommit=True,
)
cursor = connection.cursor()

def execute_script(sql: str) -> None:
    lines = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        lines.append(line)
    for statement in "\n".join(lines).split(";"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)

if reset:
    cursor.execute("DROP DATABASE IF EXISTS infobank_eval")

execute_script((root / "evaluation" / "prepare_eval_database.sql").read_text(encoding="utf-8"))
schema = (root / "infobank_db.sql").read_text(encoding="utf-8").replace("infobank_db", "infobank_eval")
execute_script(schema)
cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='infobank_eval'")
print(f"infobank_eval schema ready; table_count={cursor.fetchone()[0]}")
connection.close()
'@
        $env:INFOBANK_REPRO_RESET = $resetValue
        $script | & $Python -
        if ($LASTEXITCODE -ne 0) {
            throw "Evaluation database initialization failed."
        }
    } finally {
        Remove-Item Env:\INFOBANK_REPRO_ROOT_PASSWORD -ErrorAction SilentlyContinue
        Remove-Item Env:\INFOBANK_REPRO_RESET -ErrorAction SilentlyContinue
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

Write-Step "Environment"
Write-Host "Repository: $repoRoot"
Write-Host "OS: $([System.Environment]::OSVersion.VersionString)"
$dbEnv = Get-ComposeDbEnvironment -ComposePath (Join-Path $repoRoot "docker-compose.yml")

if (-not $SkipDocker) {
    Write-Step "MariaDB"
    $docker = Get-FirstCommand "docker"
    if ($docker) {
        & docker --version
        & docker compose version
        & docker compose up -d db
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose up -d db failed."
        }
        & docker compose ps
    } elseif (Test-LocalPort -Port 3307) {
        Write-Warning "docker CLI is not available, but 127.0.0.1:3307 is reachable. Continuing with the running MariaDB service."
    } else {
        throw "docker CLI is not available and 127.0.0.1:3307 is not reachable. Start Docker Desktop or add docker to PATH, then rerun this script."
    }

    if (-not (Test-LocalPort -Port 3307)) {
        throw "MariaDB is not reachable at 127.0.0.1:3307."
    }
    Write-Host "MariaDB port check: PASS"
}

Write-Step "Python"
$venvPython = Join-Path $repoRoot "backend_python/.venv_eval/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    $python312 = Find-Python312
    Write-Host "Creating backend_python/.venv_eval with $($python312.Command) $($python312.Arguments -join ' ') ($($python312.Version))"
    & $python312.Command @($python312.Arguments + @("-m", "venv", "backend_python/.venv_eval"))
    if ($LASTEXITCODE -ne 0) {
        throw "Virtual environment creation failed."
    }
}
& $venvPython --version

if (-not $SkipPackageInstall) {
    Write-Step "Dependencies"
    $cachePath = Join-Path $repoRoot $PipCacheDir
    New-Item -ItemType Directory -Path $cachePath -Force | Out-Null
    & $venvPython -m pip install --cache-dir $cachePath --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed."
    }
    & $venvPython -m pip install --cache-dir $cachePath -r backend_python/requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed."
    }
}

Write-Step "Dependency check"
& $venvPython -m pip check
if ($LASTEXITCODE -ne 0) {
    throw "pip check failed."
}

Write-Step "Environment files"
$normalEnv = Join-Path $repoRoot "backend_python/.env"
if ($ForceEnvFiles -or -not (Test-Path -LiteralPath $normalEnv)) {
    Copy-Item backend_python/.env.example $normalEnv -Force
    Write-Host "Created backend_python/.env from example."
} else {
    Write-Host "backend_python/.env already exists."
}

$evalEnv = Join-Path $repoRoot "backend_python/.env.eval"
if ($ForceEnvFiles -or -not (Test-Path -LiteralPath $evalEnv)) {
    $evalContent = (Get-Content backend_python/.env.eval.example -Raw).Replace("<password>", $dbEnv["MARIADB_PASSWORD"])
    Set-Content -Path $evalEnv -Value $evalContent -NoNewline
    Write-Host "Created backend_python/.env.eval for infobank_eval."
} else {
    Write-Host "backend_python/.env.eval already exists."
}

if ($PrepareEvalDatabase -or $ResetEvaluationState) {
    Write-Step "Evaluation database"
    Initialize-EvaluationDatabase -Python $venvPython -RootPassword $dbEnv["MARIADB_ROOT_PASSWORD"] -Reset ([bool]$ResetEvaluationState)

    if ($ResetEvaluationState) {
        $chromaEval = Resolve-Path (Join-Path $repoRoot "backend_python/chroma_eval") -ErrorAction SilentlyContinue
        if ($chromaEval) {
            $expected = Join-Path $repoRoot "backend_python/chroma_eval"
            if ($chromaEval.Path -ne (Resolve-Path $expected).Path) {
                throw "Refusing to remove unexpected Chroma path: $($chromaEval.Path)"
            }
            Remove-Item -LiteralPath $chromaEval.Path -Recurse -Force
            Write-Host "Removed backend_python/chroma_eval."
        }
    }
}

if ($RunUnitTests) {
    Write-Step "Unit tests"
    & $venvPython -m unittest discover -s evaluation/tests -v
    if ($LASTEXITCODE -ne 0) {
        throw "Unit tests failed."
    }
}

if ($RunPilotCheck) {
    Write-Step "Pilot CheckOnly"
    & $venvPython -m evaluation.run_document_rag_pilot `
        --check-only `
        --results-dir evaluation/results `
        --top-k 4 `
        --repetitions 1 `
        --case-ids "FULL_01,METADATA_01,DENY_01,AGG_SAFE_01,AGG_INDIVIDUAL_01,MIXED_PRIMARY_01,CONTEXT_ONLY_01" `
        --env-file backend_python/.env.eval
    if ($LASTEXITCODE -ne 0) {
        throw "Pilot CheckOnly failed."
    }
}

Write-Step "Done"
Write-Host "Reproduction bootstrap completed. For the real pilot, set OPENAI_API_KEY in the process and run evaluation/run_document_rag_pilot.ps1."
