# CRISPR Design Tool

Built a full-stack CRISPR design web platform integrating Python pipelines (CRISPRitz, RS3, CFD) with a FastAPI backend, React frontend, and Celery task queue. Deployed with Docker. Designed to manage CRISPR guide design runs and off-target results with a scalable architecture.

## Highlights
- Single-click guide design flow covering sequence validation, NGG protospacer discovery, off-target analysis, and RS3 efficacy scoring.
- Redis-backed job tracking with optimistic caching so identical design requests reuse prior results.
- Frontend dashboards for live progress monitoring, job history, and ranked guide inspection.
- Containerised services (backend API, Celery worker, Redis, Vite frontend) orchestrated via `docker compose` for reproducible local runs.

## Repository Layout
- `backend/` – FastAPI app, sequence utilities, Celery tasks, and Redis job store helpers.
- `backend/celery_app/` – Micromamba-based image definition and requirements for the worker.
- `frontend/` – Vite + React TypeScript SPA using Mantine UI and TanStack Query.
- `data/` – Local mount point for genome references, CRISPRitz indices, CFD scoring pickles, and job outputs.
- `docker-compose.yml` – Spins up Redis, backend API, Celery worker, and frontend.

## Architecture Overview
1. **Frontend (Vite dev server)** calls the backend at `POST /api/design` and immediately routes the user to a job detail page.
2. **Backend (FastAPI)** validates input, creates a job record in Redis, checks for cached results, and enqueues work on Celery.
3. **Celery worker** runs the design pipeline:
   - sanitises the sequence and finds SpCas9 NGG candidates,
   - executes `crispritz.py` against the configured genome index,
   - scores off-target hits with CFD and RS3, writing artefacts into `/data/results/<job_id>`.
   Progress is streamed back into Redis to keep the UI current.
4. **Redis** stores job metadata, cached payloads, and powers the queue/broker.

> ⚠️ **Scope:** The MVP currently supports only SpCas9 with an NGG PAM on the hg38 genome. Extending to other systems requires additional indices, scoring assets, and small code changes.

## Prerequisites
- Docker 24+ and Docker Compose plugin.
- Access to CRISPRitz assets and scoring data placed under `data/`.

## Download required data

- Download the hg38 genome (per chromosome)

`wget https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/hg38.chromFa.tar.gz && gunzip hg38.fa.gz`

- Index the genome with `crispritz.py` to get the NGG_2_hg38 directory

`crispritz.py index-genome hg38 hg38/ pam/pamNGG.txt -bMax 2 -th 4`

## Configure Environment
1. Duplicate the example settings:
   ```bash
   cp .env.example .env
   ```
2. Confirm the paths inside `.env` match the mounted files under `data/`. Required artefacts:
   | Setting | Default path | Notes |
   | --- | --- | --- |
   | `HG38_REFERENCE_FASTA` | `/data/genomes/hg38/hg38.fa` | Reference FASTA used by CRISPRitz. |
   | `CRISPRITZ_INDEX` | `/data/genomes/hg38/NGG_2_hg38` | Pre-built CRISPRitz NGG index directory. |
   | `CRISPRITZ_PAM_TXT` | `/data/PAM/pamNGG.txt` | PAM definition consumed by CRISPRitz. |
   | `CRISPRITZ_ANNOTATIONS_BED` | `/data/genomes/hg38/hg38Annotation.bed` | Optional; enriches off-target annotations. |
   | `MISMATCH_SCORES` | `/data/CFD_scoring_matrix/mismatch_score.pkl` | Pickle bundle for CFD scoring. |
   | `PAM_SCORES` | `/data/CFD_scoring_matrix/pam_scores.pkl` | Pair with mismatch scores for CFD. |
   | `CRISPRITZ_RESULTS_DIR` | `/data/results` | Output folder mounted to persist per-job files. |

## Run with Docker Compose
```bash
docker compose up --build
```
This launches Redis, the FastAPI API on `http://localhost:5001`, the Vite frontend on `http://localhost:3000`, and a Celery worker. Hot-reload is enabled via bind mounts.

### Accessing the App
- Navigate to `http://localhost:3000` to open the UI.
- The API exposes OpenAPI docs at `http://localhost:5001/docs`.

### Shutting Down
```bash
docker compose down
```
Add `--volumes` if you want to wipe Redis data between runs.

## Testing
- Backend: `RUN_INTEGRATION=1 PYTHONPATH=backend python -m pytest backend/tests`

`RUN_INTEGRATION=1` runs the larger integration tests. Do not include if you do not want to run these tests. To only run the integration tests add `-m integration` to the command.

Frontend testing to come...

## Next Steps
Potential enhancements include support for alternative nucleases/PAMs, include more off-targets information in the UI on the results page, and persistence beyond Redis (e.g., Postgres) for audit trails.

