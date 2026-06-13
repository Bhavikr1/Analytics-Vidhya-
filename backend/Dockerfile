FROM python:3.13-slim

WORKDIR /app

# lxml needs libxml2/libxslt at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

ENV CHROMA_DIR=/app/chroma_db

EXPOSE 8000

# Use shell form so Railway's $PORT variable is expanded at runtime
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
