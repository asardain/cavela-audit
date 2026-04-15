FROM python:3.13-slim

WORKDIR /app

# WeasyPrint needs system dependencies for PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi>=0.115 \
    "uvicorn[standard]>=0.32" \
    jinja2>=3.1 \
    python-multipart>=0.0.9 \
    httpx>=0.27 \
    anthropic>=0.40 \
    resend>=2.0 \
    weasyprint>=62.0 \
    markdown-it-py>=3.0

COPY app/ ./app/

EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
