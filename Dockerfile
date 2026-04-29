FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install --with-deps chromium

COPY . .

RUN mkdir -p /app/uploads

ENV FLASK_APP=run.py \
    PYTHONUNBUFFERED=1

EXPOSE 7010

CMD ["gunicorn", "--bind", "0.0.0.0:7010", "--workers", "2", "--timeout", "300", "run:app"]
