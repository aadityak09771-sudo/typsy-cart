#!/usr/bin/env bash
set -o errexit

echo "==> Running database migrations on cloud database..."
python manage.py migrate --noinput

echo "==> Loading pre-seeded catalog products..."
python manage.py loaddata initial_products.json || true

echo "==> Ensuring admin superuser exists..."
python manage.py init_admin || true

echo "==> Synchronizing dynamic categories, settings & banners..."
python sync_initial_data.py || true

echo "==> Starting Gunicorn production server..."
exec gunicorn config.wsgi:application
