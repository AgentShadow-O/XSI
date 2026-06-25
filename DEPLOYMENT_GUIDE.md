# XSI Production Deployment Guide

This guide provides instructions for deploying the XSI platform in a production environment.

## 1. Backend Deployment

### Requirements
- Python 3.10+
- PostgreSQL (Recommended for production, though SQLite is supported)
- Gunicorn/Uvicorn for serving the FastAPI application

### Environment Variables
Configure the following environment variables:
- `PRODUCTION=true`: Enables security hardening (HSTS, secure headers).
- `SECRET_KEY`: A long, random string for JWT signing.
- `DATABASE_URL`: Connection string (e.g., `postgresql://user:pass@localhost/xsi`).
- `SERVER_HOST`: Usually `0.0.0.0`.
- `SERVER_PORT`: Usually `8000`.
- `CORS_ORIGINS`: Comma-separated list of allowed frontend domains.

### Running with Gunicorn
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend.main:app --bind 0.0.0.0:8000
```

## 2. Frontend Deployment

### Build Optimization
The frontend is built using Vite, which performs tree-shaking and minification by default.

1. Configure `.env.production`:
   ```env
   VITE_API_URL=https://api.yourdomain.com
   VITE_WS_URL=wss://api.yourdomain.com/ws
   VITE_API_KEY=your-secure-agent-registration-key
   ```
2. Build the assets:
   ```bash
   cd frontend
   npm run build
   ```
3. Serve the `dist` directory using a high-performance web server like Nginx.

## 3. Nginx Configuration
Use Nginx as a reverse proxy for both the frontend and backend.

Example snippet:
```nginx
server {
    listen 443 ssl;
    server_name xsi.yourdomain.com;

    # Frontend
    location / {
        root /var/www/xsi/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSockets
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
```

## 4. Security Hardening
- **SSL/TLS:** Always use HTTPS.
- **Firewall:** Only expose ports 80 (redirect to 443) and 443.
- **Database:** Ensure the database is not publicly accessible.
- **Backups:** Schedule regular backups of the `xsi.db` (if using SQLite) or the PostgreSQL database.
