#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "Installing production requirements..."
pip install -r requirements.txt

echo "Collecting static assets with Whitenoise..."
python manage.py collectstatic --noinput

echo "Applying PostgreSQL database migrations..."
python manage.py migrate

echo "Seeding realistic UAE enterprise demo data..."
python manage.py seed_demo

echo "Build process completed successfully!"
