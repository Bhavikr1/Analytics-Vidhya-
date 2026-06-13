FROM python:3.13-slim

WORKDIR /app

# lxml needs libxml2/libxslt at runtime; build tools removed after install
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# The Chroma index must be provided at /app/chroma_db — either baked in
# (COPY chroma_db ./chroma_db), mounted as a volume, or downloaded at boot.
ENV CHROMA_DIR=/app/chroma_db

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
