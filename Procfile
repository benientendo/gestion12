web: gunicorn gestion_magazin.wsgi --log-file -
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py migrate_variant_stock_to_parent --execute
