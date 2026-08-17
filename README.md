# InfoBank Project

**Janos Lenart** // Hunti
Computer Science Student @ EKKE-IK (Eszterhazy Karoly Catholic University)

InfoBank is a research prototype for governed personal-data access, Role-Aware RAG, EvidenceUnits, source-role tracing, and controlled failure.

This repository currently provides a Python FastAPI backend and a static HTML/CSS/JS frontend. These instructions are for starting the prototype locally from a clean checkout; they are not a benchmark or scientific evaluation procedure.

## Requirements

- Git
- Python 3.12
- Docker with Docker Compose, for the MariaDB database
- A modern browser

The frontend is static and uses CDN-hosted Tailwind, Font Awesome, D3, and Google Fonts.

## Clone

```bash
git clone https://github.com/hunti-ekke/InfoBank_LJ.git
cd InfoBank_LJ
```

## Backend Environment

Create and activate a virtual environment:

```bash
cd backend_python
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install the pinned dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

`pip check` should report:

```text
No broken requirements found.
```

## Configuration

Copy the example backend environment file:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Mandatory startup variables:

- `DATABASE_URL`: SQLAlchemy URL for the MariaDB database.
- `JWT_SECRET_KEY`: local JWT signing secret.

Optional variables:

- `OPENAI_API_KEY`: required only for OpenAI-backed document ingestion, embeddings, and chat generation. The backend can start and expose `/docs` and non-AI endpoints without it.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`: required only for Gmail OAuth connector flows.
- `APP_BASE_URL`: optional base URL for connector callback construction.

Do not commit real secrets. `.env` is ignored by Git.

## Database

The intended local database is MariaDB/MySQL. The included Compose file starts MariaDB 11.4 and initializes the schema from `infobank_db.sql`.

From the repository root:

```bash
docker compose up -d db
```

Default local database settings:

- Engine: MariaDB 11.4
- Database: `infobank_db`
- User: `infobank`
- Password: `infobank_dev_password`
- Host port: `3307`
- Container port: `3306`
- SQLAlchemy URL:

```text
mysql+pymysql://infobank:infobank_dev_password@127.0.0.1:3307/infobank_db?charset=utf8mb4
```

The first container startup applies `infobank_db.sql` automatically. The FastAPI app also calls SQLAlchemy `create_all()` during startup, so new tables declared by the models are created if missing. For databases created before the CITDS 11 changes, see `backend_python/migrations/citds_11_mysql.sql`.

To recreate the local database from scratch:

```bash
docker compose down -v
docker compose up -d db
```

## Start the Backend

From `backend_python` with the virtual environment activated:

```bash
uvicorn main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Test database connectivity:

```text
http://127.0.0.1:8000/api/test-db
```

Expected response shape:

```json
{"status":"success","users_in_db":0}
```

The exact user count may differ after registration or tests.

## Serve the Frontend

The frontend is static; no Node build step is required.

From the repository root:

```bash
cd frontend
python -m http.server 8080 --bind 127.0.0.1
```

Open:

```text
http://127.0.0.1:8080/index.html
```

The frontend calls the backend at:

```text
http://127.0.0.1:8000/api
```

Keep the backend running while using the frontend.

## Research Evaluation Status

The repository currently contains a pre-pilot research evaluation state. The
production prototype, isolated evaluation environment, three-mode document-RAG
harness, 40-case synthetic fixture set, and manual seven-case pilot runner are
available. Real final benchmark results are not yet published.

See:

- [Evaluation status](docs/evaluation/STATUS.md)
- [Independent reproduction guide](docs/evaluation/INDEPENDENT_REPRODUCTION.md)
- [Functional validation summary](docs/evaluation/FUNCTIONAL_VALIDATION.md)
- [Paper-ready reproduction section](docs/evaluation/PAPER_REPRODUCTION_SECTION.md)
- [Evaluation harness README](evaluation/README.md)
- [Fixture README](evaluation/fixtures/README.md)

## Optional Integrations

### OpenAI

Set `OPENAI_API_KEY` in `backend_python/.env` to use document ingestion, embeddings, and generated chat answers.

Without this key:

- the backend still starts;
- `/docs` and `/api/test-db` remain available;
- OpenAI-dependent endpoints fail locally with a clear missing-key error when invoked.

### Gmail OAuth

Set these values in `backend_python/.env` only when testing Gmail OAuth:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/connectors/gmail/callback
```

The Gmail API must also be enabled in the corresponding Google Cloud project.

## License

This project is licensed under the CC BY-NC 4.0 License. See [LICENSE](LICENSE) for details.

[![License: CC BY-NC 4.0](https://licensebuttons.net/l/by-nc/4.0/80x15.png)](https://creativecommons.org/licenses/by-nc/4.0/)
