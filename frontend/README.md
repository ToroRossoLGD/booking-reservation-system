# Bookica frontend

React, TypeScript, and Vite client for the booking reservation API.

## Local development

From this directory:

```bash
npm install
npm run dev
```

The app runs at `http://localhost:5173` and proxies `/api` requests to the backend
at `http://localhost:8000`.

To launch the complete stack from the repository root:

```bash
docker compose up --build
```

## Checks

```bash
npm run lint
npm run build
```

Copy `.env.example` to `.env` only when you need to override the API or proxy URL.
