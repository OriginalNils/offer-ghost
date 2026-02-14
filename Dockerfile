# Python 3.11 Slim Image (klein und schnell)
FROM python:3.11-slim

# Arbeitsverzeichnis im Container
WORKDIR /app

# System-Dependencies installieren (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python Requirements kopieren
COPY requirements.txt .

# Python Packages installieren
RUN pip install --no-cache-dir -r requirements.txt

# App-Code kopieren
COPY . .

# Data-Verzeichnis erstellen
RUN mkdir -p /app/data /app/data/products /app/data/sniper

# Healthcheck hinzufügen
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/status || exit 1

# Port exposieren
EXPOSE 5000

# Start-Command mit Gunicorn (Production-Server)
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "--timeout", "120", "--access-logfile", "-", "src.api.server:app"]
