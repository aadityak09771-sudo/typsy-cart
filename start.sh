#!/usr/bin/env bash
set -o errexit

cd backend
echo "==> Running database migrations on cloud database..."
python manage.py migrate --noinput

echo "==> Loading pre-seeded catalog products..."
python manage.py loaddata initial_products.json || true

echo "==> Starting Gunicorn production server..."
exec gunicorn config.wsgi:application
