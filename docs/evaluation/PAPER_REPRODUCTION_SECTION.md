# Paper Reproduction Section

## Magyar

A kísérleti prototípust a `pre-pilot-v0.1` Git tag állapotából reprodukáltuk.
A futtatáshoz Windows PowerShell, Python 3.12, Docker Desktop Docker Compose
támogatással, valamint egy lokális MariaDB szolgáltatás szükséges. A MariaDB
konténer a repository `docker-compose.yml` fájljával indítható, és a fejlesztői
adatbázist a `127.0.0.1:3307` címen szolgálja ki. A normál indítás ellenőrzése
a Python 3.12 virtuális környezet létrehozásából, a rögzített
`backend_python/requirements.txt` függőségek telepítéséből, a `pip check`
futtatásából, a FastAPI backend indításából, valamint a `/docs` és
`/api/test-db` végpontok ellenőrzéséből áll. A statikus frontend külön build
nélkül, a `frontend` könyvtárból indított lokális HTTP szerverrel vizsgálható.

Az értékelés a normál fejlesztői állapottól izolált környezetben fut. Ehhez az
`infobank_eval` MariaDB adatbázist, a `backend_python/chroma_eval` Chroma
perzisztencia-könyvtárat és a `backend_python/.venv_eval` Python környezetet
használjuk. A `backend_python/.env.eval` fájlban a `DATABASE_URL` értékének az
`infobank_eval` adatbázisra, a `CHROMA_PERSIST_DIR` értékének pedig
`./chroma_eval` útvonalra kell mutatnia. Az OpenAI API-kulcs nem kerülhet
konfigurációs fájlba; azt kizárólag a futtató PowerShell folyamat
`OPENAI_API_KEY` környezeti változójaként kell megadni. A repository tartalmaz
egy reprodukciós bootstrap scriptet, amely a lokális függőségek telepítését,
az izolált adatbázis előkészítését, az unit tesztek futtatását és a pilot
előellenőrzését automatizálja:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\evaluation\bootstrap_reproduction.ps1 -PrepareEvalDatabase -RunUnitTests -RunPilotCheck
```

A valós pilot futtatása előtt az evaluation adatbázisnak és a Chroma
könyvtárnak tisztának kell lennie. A pilot a `document_rag_v1` fixture készlet
hét előre rögzített esetét futtatja három módban:
`standard_rag`, `governance_only_rag` és `role_aware_rag`. Minden esetben egy
közös retrieved candidate lista kerül felhasználásra mindhárom módhoz. A pilot
egy ismétléssel fut, ezért siker esetén 7 x 3 x 1, azaz 21 nyers
eredményrekord keletkezik az `evaluation/results/pilot_<UTC timestamp>/`
könyvtárban. A futás fő artifactjai: `results.jsonl`, `run_manifest.json`,
`fixture_subset_manifest.json`, `shared_retrieval.jsonl` és
`pilot_inspection.json`. A valós pilot parancsa:

```powershell
.\evaluation\run_document_rag_pilot.ps1
```

## English

The experimental prototype was reproduced from the `pre-pilot-v0.1` Git tag.
The runtime environment requires Windows PowerShell, Python 3.12, Docker
Desktop with Docker Compose support, and a local MariaDB service. The MariaDB
container is started from the repository `docker-compose.yml` file and exposes
the development database at `127.0.0.1:3307`. Normal startup validation consists
of creating a Python 3.12 virtual environment, installing the pinned
`backend_python/requirements.txt` dependencies, running `pip check`, starting
the FastAPI backend, and checking the `/docs` and `/api/test-db` endpoints. The
static frontend requires no build step and can be inspected through a local HTTP
server started from the `frontend` directory.

The evaluation is executed in an environment isolated from the normal
development state. It uses the `infobank_eval` MariaDB database, the
`backend_python/chroma_eval` Chroma persistence directory, and the
`backend_python/.venv_eval` Python environment. In `backend_python/.env.eval`,
`DATABASE_URL` must point to `infobank_eval`, and `CHROMA_PERSIST_DIR` must be
set to `./chroma_eval`. The OpenAI API key must not be stored in configuration
files; it is supplied only through the `OPENAI_API_KEY` environment variable in
the PowerShell process that runs the pilot. The repository includes a
reproduction bootstrap script that automates local dependency installation,
isolated database preparation, unit tests, and the pilot preflight check:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\evaluation\bootstrap_reproduction.ps1 -PrepareEvalDatabase -RunUnitTests -RunPilotCheck
```

Before running the real pilot, the evaluation database and Chroma directory must
be clean. The pilot executes seven fixed cases from the `document_rag_v1`
fixture set across three modes: `standard_rag`, `governance_only_rag`, and
`role_aware_rag`. For each case, the same retrieved candidate list is reused
across all three modes. With one repetition, a successful pilot therefore
produces 7 x 3 x 1, or 21, raw result records under
`evaluation/results/pilot_<UTC timestamp>/`. The main artifacts are
`results.jsonl`, `run_manifest.json`, `fixture_subset_manifest.json`,
`shared_retrieval.jsonl`, and `pilot_inspection.json`. The real pilot is
started with:

```powershell
.\evaluation\run_document_rag_pilot.ps1
```
