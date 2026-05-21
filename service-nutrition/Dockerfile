FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl dos2unix && rm -rf /var/lib/apt/lists/*

COPY shared/ /tmp/shared/
RUN pip install --no-cache-dir /tmp/shared/

COPY service-nutrition/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY service-nutrition/ .
RUN dos2unix entrypoint.sh && chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
