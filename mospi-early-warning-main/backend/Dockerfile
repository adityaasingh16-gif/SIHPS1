# ---------- Stage 1: build the React SPA ----------
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: python runtime (API + SPA from one process) ----------
FROM python:3.11-slim

WORKDIR /app

# Install system C/C++ dependencies for compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy backend (includes ML package src, app, models, panel CSV)
COPY backend /app/backend

# Copy the production SPA build so the API serves the UI single-origin
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Runtime defaults (overridable via compose or command line)
ENV FRONTEND_DIST=/app/frontend/dist \
    MODEL_DIR=/app/backend/models \
    DATABASE_URL=sqlite:////app/data/mospi_ew.db \
    UPLOAD_DIR=/app/backend/uploads \
    AUTO_SEED_DATABASE=true

# Persistent data location (kept outside the image for named-volume mounts)
RUN mkdir -p /app/data /app/backend/uploads

# Use the sanitized pre-seed when a deployment package provides it. Generated
# database files are excluded from Git, so clean checkouts use the existing
# AUTO_SEED_DATABASE first-start path instead.
RUN if [ -f /app/backend/data/seed_mospi_ew.db ]; then \
      cp /app/backend/data/seed_mospi_ew.db /app/data/mospi_ew.db; \
    fi

WORKDIR /app/backend

EXPOSE 8000

# Bind to Render's $PORT when present (hosts like Render inject it), else 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
