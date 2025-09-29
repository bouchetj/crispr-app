# Backend Service

This directory contains the FastAPI application, Celery task definitions, and supporting utilities that power the CRISPR design pipeline.

## Key paths
- `api/`: FastAPI routers, dependency wiring, and request/response models.
- `celery_app/`: Celery application bootstrap, worker Dockerfile, and supporting scripts.
- `core/`: Shared configuration helpers and common utilities.
- `docker/`: Entrypoint scripts and runtime shell helpers used by the container image.
- `schemas/`: Pydantic models for validating payloads exchanged with the API and tasks.
- `services/`: Domain services that orchestrate guide discovery, scoring, and persistence.
- `store/`: Data-access layer and cache helpers for Redis-backed job metadata.
- `tasks/`: Celery task entry points for guide discovery, scoring, and result aggregation.
- `tests/`: Pytest suite covering API endpoints and worker logic.

## Local development
The backend container is started through `./manage.sh --env dev up`. Environment variables are loaded from `.env.dev`; copy `.env.example` to create it and supply real secrets before running the stack.
