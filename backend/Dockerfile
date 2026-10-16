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

# WITH_CUDA=true (docker-compose.gpu.yml) instala las librerias CUDA/cuDNN de NVIDIA (varios GB);
# en CPU se omiten y Whisper usa int8 sin ellas.
ARG WITH_CUDA=false
COPY requirements.txt .
RUN if [ "$WITH_CUDA" = "true" ]; then cp requirements.txt /tmp/requirements.txt; \
    else grep -v '^nvidia-' requirements.txt > /tmp/requirements.txt; fi && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

RUN pip install --no-cache-dir gunicorn

# NER clinico en CPU (ver requirements-ner.txt). Capa aparte para no reinstalar torch al cambiar requirements.txt.
COPY requirements-ner.txt .
RUN pip install --no-cache-dir -r requirements-ner.txt

COPY . .
# Las migraciones deben estar versionadas en el repo; en runtime el entrypoint ejecuta migrate

# La cache de Hugging Face (modelos Whisper) se monta como volumen: debe existir y ser de appuser.
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app \
    && mkdir -p /home/appuser/.cache/huggingface && chown -R appuser:appuser /home/appuser/.cache

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