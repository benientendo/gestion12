@echo off
scalingo --app gestionnumerique run python manage.py shell < check_boutique.py
