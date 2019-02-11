cd /home/site/wwwroot
. antenv/bin/activate
python -m celery worker -A api.app.celery --loglevel=INFO -E