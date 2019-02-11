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
- To get a token: POST --user user:password "http://localhost:5000/tokens"
- To queue a new ain for processing: POST -H "Authorization: Bearer access_token" http://localhost:5000/process?ain=ain&callback_url=http://localhost:5000/debug_callback
- To check status of a task: GET -H "Authorization: Bearer <access_token>" http://localhost:5000/status/task_id
- To load monitoring webapp http://localhost:5555


The overall picture: the user provides a case number and a callback URL.  The api returns a transcription of the call, as well as extracted location and date information.

We are running a flask app with three routes:
1. process/
              This route gets the case number and callback url (for debugging, callback_url is "debug_callback")
              It returns the ain, the task_id, and the state.
              Before returning, it kicks off the following chain of tasks handled by celery asynchronously:
                           a. Schedules a call with Twilio
                           b. Checks that the call is done after an interval
                           c. Fetches the recording  of the call from Twilio
                           d. Transcribes this recording (using Google speech to text for the moment)
                           e. Deletes the recording on Twilio
                           f. Extracts date, location info
                           g. Sends a dictionary with transcription text and extracted date and location info to the callback url.       
2. status/
              This route gets the task_id, and returns the status (e.g. "calling", "transcribing", "transcribing_failed")
3. debug_callback
              Prints dictionary with court hearing date and location, and a status code (200 or 400).  You should be able to see this in the task logs.  In practice, the client would provide the callback url themselves.  This one just exists for debugging purposes.

All of the code for the above is in the api/ folder.

Located in the workflow/ folder are the implementations of the tasks:
- Calling the gov number via Twilio (in the call folder)
- Transcribing the raw recording (in the transcribe folder)
- Extracting date and location information (in the extract folder)

Unit tests for these modules are provided in the tests/ folder (work in progress).
