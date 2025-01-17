#!/bin/sh

#until cd /src/
#do
#    echo "Waiting for server volume..."
#done


until python manage.py migrate
do
    echo "Waiting for db to be ready..."
    sleep 2
done


python manage.py collectstatic --noinput

# python manage.py createsuperuser --noinput

gunicorn netology_pd_diplom.wsgi:application --bind 0.0.0.0:8000 --workers 4 --threads 4
