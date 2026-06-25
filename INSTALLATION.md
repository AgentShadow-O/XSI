# XSI Installation Guide

## Requirements
- Python 3.10+
- Node.js 18+

## Backend Setup
1. Create virtual environment: `python -m venv venv`
2. Activate: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Linux)
3. Install dependencies: `pip install -r requirements.txt`
4. Configure `config.yaml` as needed.
5. Run server: `python -m backend.main`

## Frontend Setup
1. Navigate to `frontend` directory.
2. Install dependencies: `npm install`
3. Configure `.env`: Set `VITE_API_URL` to backend URL (default `http://127.0.0.1:8000`).
4. Start dev server: `npm run dev`
