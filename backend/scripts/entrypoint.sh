#!/bin/bash
set -e

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

echo "Ejecutando migraciones de Django..."
python manage.py makemigrations accounts patients triage --noinput
python manage.py migrate --noinput

echo "Creando usuario demo si no existe..."
python manage.py create_demo_user

echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput --clear
echo "Inicio completado"

exec "$@"