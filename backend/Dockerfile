# Build context: repository root.  docker build -f backend/Dockerfile .
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 aeropulse
WORKDIR /srv
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r backend/requirements.txt
COPY ml/__init__.py ml/data.py ml/features.py ml/inference.py ml/
COPY ml/artifacts ml/artifacts
COPY data/samples data/samples
COPY backend backend
ENV PYTHONPATH=/srv:/srv/backend PYTHONUNBUFFERED=1 APP_ENV=production
USER aeropulse
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=10 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
WORKDIR /srv/backend
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
