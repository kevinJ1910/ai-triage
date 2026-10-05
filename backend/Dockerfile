FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    postgresql-client \
    redis-tools \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir gunicorn

COPY . .
# Las migraciones deben estar versionadas en el repo; en runtime el entrypoint ejecuta migrate

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Configure entrypoint script
RUN dos2unix /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/entrypoint.sh
RUN chown appuser:appuser /app/scripts/entrypoint.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health_check/ || exit 1

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
# El estado compartido (cache clinica, contexto ASR, throttling) vive en Redis, por lo que se pueden
# usar varios procesos web; los hilos esperan a los workers de inferencia sin consumir CPU.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "8", "--timeout", "120", "config.wsgi:application"]