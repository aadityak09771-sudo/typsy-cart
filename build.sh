#!/usr/bin/env bash
set -o errexit

cd backend
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py loaddata initial_products.json || true
