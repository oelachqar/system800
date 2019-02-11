# system800


How run API locally for debugging:
``` bash
    python run.py
```

How run celery worker locally for debugging:
``` bash
    celery worker -A api.app.celery --pool=solo --loglevel=INFO -E
```

How run celery monitoring webapp flower locally:
``` bash
    celery flower -A api.app.celery
```

Tips for local development:
- To get a token: POST --user <user>:<password> "http://localhost:5000/tokens"
- To queue a new ain for processing: POST -H "Authorization: Bearer <access_token>" http://localhost:5000/process?ain=ain&callback_url=http://localhost:5000/debug_callback
- To check status of a task: GET -H "Authorization: Bearer <access_token>" http://localhost:5000/status/task_id
- To load monitoring webapp http://localhost:5555
