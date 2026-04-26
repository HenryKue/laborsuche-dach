FROM node:20-alpine AS frontend-builder

WORKDIR /build

COPY web-app/package*.json ./
RUN npm ci

COPY web-app/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/

COPY --from=frontend-builder /build/dist ./frontend_dist

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]