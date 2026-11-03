# Dudamel en un solo contenedor: la interfaz compilada y la API en el mismo origen
# (app.api.publico). Para Render y servicios parecidos; todo por API (sin Ollama).

# 1. Interfaz: build en modo «publico» (llama a /api en el mismo origen)
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx vite build --mode publico

# 2. Backend
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend/app backend/app
COPY data data
COPY docs docs
COPY --from=web /web/dist frontend/dist
WORKDIR /app/backend
EXPOSE 10000
# Render pasa el puerto en $PORT
CMD ["sh", "-c", "exec uvicorn app.api.publico:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*'"]
