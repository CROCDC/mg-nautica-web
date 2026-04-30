FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Preserve uploads in a separate dir so entrypoint can sync them to the named volume
RUN mkdir -p /app/uploads_baked && \
    (cp -r /app/uploads/. /app/uploads_baked/ 2>/dev/null || true) && \
    mkdir -p /app/uploads

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV FLASK_APP=run.py \
    PYTHONUNBUFFERED=1

EXPOSE 7010

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:7010", "--workers", "2", "--timeout", "300", "run:app"]
