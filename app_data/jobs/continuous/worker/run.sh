cd /home/site/wwwroot
python -m celery worker -A api.app.celery --loglevel=INFO -E