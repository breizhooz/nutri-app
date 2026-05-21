FROM python:3.12-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONPATH=/app

COPY shared/ /tmp/shared/
RUN pip install --no-cache-dir /tmp/shared/

COPY service-recipe/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY service-recipe/ .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
