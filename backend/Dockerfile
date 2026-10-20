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
COPY manage.py manage.py
# One math thread: under a 0.1-CPU quota extra OpenMP threads only burn the budget. Fewer malloc arenas = less RSS.
ENV PYTHONPATH=/srv:/srv/backend PYTHONUNBUFFERED=1 APP_ENV=production OMP_NUM_THREADS=1 MALLOC_ARENA_MAX=2
USER aeropulse
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=10 CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health')"
WORKDIR /srv/backend
# One process for migrate + seed + serve: on a 0.1-CPU host each extra interpreter re-pays ~30 s of imports.
CMD ["python", "/srv/manage.py", "start"]
