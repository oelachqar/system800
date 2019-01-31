# system800


How run API locally for debugging:
``` bash
    python run.py
```

How run celery worker locally for debugging:
``` bash
    celery -A api.app.celery worker --pool=solo --loglevel=INFO -E
```

How run celery monitoring webapp flower locally:
``` bash
    celery flower -A api.app.celery
```

Tips for local development:
- To queue a new ain for processing: POST http://localhost:5000/process?ain=ain
- To check status of a task: GET http://localhost:5000/status/task_id
- To load monitoring webapp http://localhost:5555
