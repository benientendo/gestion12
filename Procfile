web: daphne gestion_magazin.asgi:application --port $PORT --bind 0.0.0.0 -v1
worker: celery -A gestion_magazin worker --loglevel=info --concurrency=2
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py migrate_variant_stock_to_parent --execute
