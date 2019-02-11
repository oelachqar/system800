cd /home/site/wwwroot
celery worker -A api.app.celery --loglevel=INFO -E