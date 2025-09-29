# Frontend Application

This React + Vite single-page app provides the user interface for submitting CRISPR design jobs, tracking progress, and browsing results.

## Project structure
- `src/`: Application source code written in TypeScript.
- `nginx.conf`: Nginx configuration used in the production image to serve the built app.

## Development
The dev server runs inside the Docker stack via `./manage.sh --env dev up`. Hot-module reloading is enabled so local changes refresh automatically. Environment variables such as `VITE_API_URL` are loaded from `.env.dev`.
