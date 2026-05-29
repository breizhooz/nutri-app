FROM python:3.12-slim

<<<<<<< Updated upstream
RUN apt-get update && apt-get install -y curl fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
=======
# curl: healthcheck ; libpango/libpangoft2 + fonts: dépendances natives de WeasyPrint (export PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
>>>>>>> Stashed changes

WORKDIR /app

ENV PYTHONPATH=/app

COPY shared/ /tmp/shared/
RUN pip install --no-cache-dir /tmp/shared/

COPY service-menu/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY service-menu/ .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
