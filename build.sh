#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "Installing production requirements..."
pip install -r requirements.txt

echo "Collecting static assets with Whitenoise..."
python manage.py collectstatic --noinput

echo "Build process completed successfully!"
