#!/bin/sh

until cd /src/
do
    echo "Waiting for server volume..."
done

celery -A celery_app.celery_app worker --loglevel=info