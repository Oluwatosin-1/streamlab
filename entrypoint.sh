#!/bin/sh
# entrypoint.sh

# Run Django migrations
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# Start Gunicorn
exec gunicorn streamlab.wsgi:application --bind 0.0.0.0:8000
