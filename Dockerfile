FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements/ ./requirements/
RUN pip install -r requirements/requirements-entrega.txt
COPY src/ ./src/
COPY reports/ ./reports/
COPY docs/ ./docs/
COPY assets/ ./assets/
COPY imgs/ ./imgs/
COPY entrega_v8/README_ENTREGA.md entrega_v8/DOCUMENTO_TECNICO_V8.pdf ./entrega_v8/
COPY --from=frontend /build/dist ./frontend/dist
RUN useradd --create-home app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/bootstrap', timeout=4)"
CMD ["python", "src/dashboard_api.py", "--host", "0.0.0.0", "--port", "8000"]
