# XSI Cybersecurity Platform

XSI is an Extended Security Intelligence platform for endpoint monitoring, SIEM event collection, device management, XDR-style detections, and IPS response workflows.

## Architecture

- **Frontend:** React + Vite dashboard in `frontend/` for SIEM, alerts, endpoints, deployment, and settings.
- **Backend:** FastAPI controller in `backend/` with API routes, authentication, storage, detection, prevention, sensors, and agent communication.
- **Agents:** Windows agent in `windows/`, Android agent in `android/`, and shared agent helpers in `backend/agents/`.
- **Deployment:** Cloud and container deployment assets in `deployment/`.

## Development Setup

Backend:

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Create environment files from the examples before running production-like deployments:

- `backend/.env.example`
- `frontend/.env.example`

## Backend Environment Variables

- `ENVIRONMENT=production`
- `DATABASE_URL`
- `SECRET_KEY`
- `API_KEY`
- `XSI_AGENT_TOKEN`
- `FRONTEND_URL`
- `CORS_ORIGINS`
- `API_BASE_URL`
- `LOG_LEVEL`
- `REDIS_URL`

## Frontend Environment Variables

- `VITE_API_URL`
- `VITE_WS_URL` optional; derived from `VITE_API_URL` when omitted.

## Production Deployment

Render backend:

```bash
pip install -r requirements.txt
gunicorn backend.main:app -k uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:$PORT
```

Vercel frontend:

```bash
cd frontend
npm install
npm run build
```

Set `FRONTEND_URL` and `CORS_ORIGINS` on Render to the exact Vercel URL. Set `VITE_API_URL` on Vercel to the Render backend URL.

## Health Check

```bash
curl https://your-backend.example.com/health
```
