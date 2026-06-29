#!/bin/bash
set -e

echo "Esperando a que PostgreSQL esté disponible..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q' 2>/dev/null; do
    echo "PostgreSQL no disponible - esperando 2 segundos..."
    sleep 2
done
echo "PostgreSQL está disponible"

echo "Esperando a que Redis esté disponible..."
until redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>/dev/null | grep -q PONG; do
    echo "Redis no disponible - esperando 2 segundos..."
    sleep 2
done
echo "Redis está disponible"

echo "Ejecutando migraciones de Django..."
python manage.py migrate --noinput

echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput --clear

echo "Inicio completado"