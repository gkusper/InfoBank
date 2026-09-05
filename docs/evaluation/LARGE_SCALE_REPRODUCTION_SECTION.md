# Large-Scale D1-D8 Reproduction Section

## Magyar valtozat

A vegso D1-D8 ertekeles az `d1-d8-large-scale-final-evaluation` agon futtathato. A kiserlet elkulonitett MariaDB adatbazist (`infobank_eval`) es elkulonitett Chroma tarat (`backend_python/chroma_eval`) hasznal; a fejlesztoi `infobank_db` es `chroma_data` kornyezetek hasznalata ervenytelen futasnak minosul. A Python kornyezet a `backend_python/.venv_eval` virtual environment, Python 3.12-vel es a rogzitett backend fuggesekkel. A valos D1-D5 futas OpenAI API-kulcsot igenyel, amelyet csak lokalis folyamatkornyezeti valtozokent szabad megadni.

Reprodukciohoz a kutato eloszor inditsa el a MariaDB szolgaltatast Docker Compose-zal, keszitse elo az eval kornyezetet, majd futtassa a benchmarkvalidaciot:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\evaluation\bootstrap_reproduction.ps1 -PrepareEvalDatabase -RunUnitTests -RunPilotCheck
.\evaluation\run_d1_d8_large_scale.ps1 -ValidateBenchmarks
.\evaluation\run_d1_d8_large_scale.ps1 -CheckOnly
```

A vegso real-API futas:

```powershell
$env:OPENAI_API_KEY = "<helyileg beallitott kulcs>"
.\evaluation\run_d1_d8_large_scale.ps1 -RealApi -Resume
```

A `-CheckOnly` tiszta, futas elotti allapotot ellenoriz. Egy sikeres teljes futas utan szandekosan hibazik, amig az izolalt evaluation adatbazist es Chroma tarat nem allitjak vissza, mert a clean-state guard latja a betoltott benchmark dokumentumokat es vektorokat.

A dokumentum-RAG resz `document_rag_v3` alatt 400 D1-D5 esetet futtat harom modban es ot ismetlessel, igy 6000 meresi rekordot varunk. Az EvidenceUnit holdout `data/benchmarks/evidence_unit_v2_holdout/` alatt 340 D6-D8 esetet futtat harom tiszta adatbazis-ismetlessel, igy 1020 rekordot varunk. A teljes sikeres futas legalabb 7020 meresi rekordot, manifeszteket, determinisztikus pontozast, statisztikai teszteket es szanitizalt publikacios csomagot hoz letre az `evaluation/results/d1_d8_large_scale_<UTC>/` es `evaluation/publication_results/d1_d8_large_scale_v1/` konyvtarakban.

## English Version

The final D1-D8 evaluation is run from the `d1-d8-large-scale-final-evaluation` branch. The experiment uses an isolated MariaDB database (`infobank_eval`) and an isolated Chroma store (`backend_python/chroma_eval`); using the development `infobank_db` database or `chroma_data` store invalidates the run. The Python runtime is `backend_python/.venv_eval` with Python 3.12 and pinned backend dependencies. The real D1-D5 phase requires an OpenAI API key, supplied only as a local process environment variable.

To reproduce the evaluation, start MariaDB with Docker Compose, prepare the evaluation runtime, validate the frozen benchmarks, and run preflight:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\evaluation\bootstrap_reproduction.ps1 -PrepareEvalDatabase -RunUnitTests -RunPilotCheck
.\evaluation\run_d1_d8_large_scale.ps1 -ValidateBenchmarks
.\evaluation\run_d1_d8_large_scale.ps1 -CheckOnly
```

The final real-API run is:

```powershell
$env:OPENAI_API_KEY = "<set locally>"
.\evaluation\run_d1_d8_large_scale.ps1 -RealApi -Resume
```

`-CheckOnly` is a pre-run clean-state check. After a successful full run it intentionally fails until the isolated evaluation database and Chroma store are reset, because the clean-state guard detects the loaded benchmark documents and vectors.

The document-RAG phase evaluates `document_rag_v3`, containing 400 D1-D5 cases, under three modes with five repetitions, for 6000 measured records. The EvidenceUnit holdout in `data/benchmarks/evidence_unit_v2_holdout/` evaluates 340 D6-D8 cases across three clean database repetitions, for 1020 measured records. A complete successful run therefore produces at least 7020 measured records, manifests, deterministic scores, statistical tests, and a sanitized publication package under `evaluation/results/d1_d8_large_scale_<UTC>/` and `evaluation/publication_results/d1_d8_large_scale_v1/`.
