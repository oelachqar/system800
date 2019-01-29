# system800


How run API locally for debugging:
``` bash
    python run.py 
``` 

How run celery worker locally for debugging:
``` bash
    celery -A api.app.celery worker --pool=solo --loglevel=INFO -E
``` 

API
- To queue a new ain for processing: POST http://localhost:5000/process?ain=ain
- To check status: GET http://localhost:5000/status/task_id
