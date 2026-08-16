#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py createcachetable
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-3}" \
    --worker-class sync \
    --max-requests 1000 \
    --max-requests-jitter 100
