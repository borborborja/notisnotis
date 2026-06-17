#!/bin/sh
set -e

echo "→ Migraciones"
python manage.py migrate --noinput

echo "→ Estáticos"
python manage.py collectstatic --noinput

exec "$@"
