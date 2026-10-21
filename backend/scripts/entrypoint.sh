#!/bin/bash
set -e

# Dynamically locate site-packages and prepend CUDA runtime libraries to LD_LIBRARY_PATH
PYTHON_SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")
if [ -d "$PYTHON_SITE_PACKAGES/nvidia/cublas/lib" ] || [ -d "$PYTHON_SITE_PACKAGES/nvidia/cudnn/lib" ]; then
    export LD_LIBRARY_PATH=$PYTHON_SITE_PACKAGES/nvidia/cublas/lib:$PYTHON_SITE_PACKAGES/nvidia/cudnn/lib:${LD_LIBRARY_PATH:-}
    echo "Enlazadas dinámicamente las librerías de CUDA/cuDNN de nvidia-* pip packages a LD_LIBRARY_PATH."
else
    echo "No se encontraron librerías CUDA/cuDNN de nvidia-* pip packages en $PYTHON_SITE_PACKAGES."
fi

echo "Esperando a que PostgreSQL esté disponible..."
until PGPASSWORD=$DATABASE_PASSWORD psql -h "$DATABASE_HOST" -U "$DATABASE_USER" -d "$DATABASE_NAME" -c '\q'; do
    echo "PostgreSQL no disponible - esperando 2 segundos..."
    sleep 2
done
echo "PostgreSQL está disponible"

echo "Esperando a que Redis esté disponible..."
until redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping | grep -q PONG; do
    echo "Redis no disponible - esperando 2 segundos..."
    sleep 2
done
echo "Redis está disponible"

# Los workers Celery comparten imagen pero no deben migrar ni recolectar estaticos en paralelo
# con el backend: arrancan cuando el backend ya esta sano (RUN_STARTUP_TASKS=False).
if [ "${RUN_STARTUP_TASKS:-True}" = "True" ]; then
    echo "Ejecutando migraciones de Django..."
    python manage.py migrate --noinput

    echo "Creando usuario demo si no existe..."
    python manage.py create_demo_user

    echo "Recolectando archivos estáticos..."
    python manage.py collectstatic --noinput --clear
fi
echo "Inicio completado"

exec "$@"