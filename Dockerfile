FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN groupadd --system audit && useradd --system --gid audit --home-dir /app audit
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && python -m pip install --requirement /app/requirements.txt
COPY backend /app/backend
RUN mkdir -p /app/backend/audit_repo && chown -R audit:audit /app
USER audit
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import json,urllib.request; response=urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=3); data=json.load(response); raise SystemExit(0 if response.status==200 and data.get('status')=='ready' else 1)"
CMD ["uvicorn","backend.main:app","--host","0.0.0.0","--port","8000","--no-access-log"]
