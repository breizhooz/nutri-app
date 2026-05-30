FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    curl \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONPATH=/app

COPY shared/ /tmp/shared/
RUN pip install --no-cache-dir /tmp/shared/

# torch/torchvision CPU-only (évite les wheels CUDA ~2,5 Go tirés par défaut par easyocr).
RUN pip install --no-cache-dir \
    torch==2.3.1 torchvision==0.18.1 \
    --index-url https://download.pytorch.org/whl/cpu

COPY service-crawler/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pré-télécharge les modèles EasyOCR (détection + reconnaissance latin) dans l'image
# pour éviter une latence/dépendance réseau au premier scan.
RUN python -c "import easyocr; easyocr.Reader(['fr','en'], gpu=False)"

COPY service-crawler/ .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
