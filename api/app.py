from uuid import uuid4

from celery import chain
from celery.result import AsyncResult

from config import Config

from flask import Flask, jsonify, request

from .celery_app import make_celery

from .tasks import (
    ExtractInfo,
    InitiateCall,
    PullRecording,
    SendResult,
    TranscribeCall,
    logger,
)


#
# Init apps
#
app = Flask(__name__)
app.config.update(
    CELERY_BROKER_URL=Config.celery_broker,
    CELERY_RESULT_BACKEND=Config.celery_result_backend,
)

celery = make_celery(app, name="app")
call = celery.register_task(InitiateCall())
get_recording_uri = celery.register_task(PullRecording())
extract_info = celery.register_task(ExtractInfo())
transcribe = celery.register_task(TranscribeCall())
send_result = celery.register_task(SendResult())


@celery.task()
def send_error(request, exc, traceback, ain, callback_url):
    """
    Inform caller of errors.
    Using the link_error example here which explains first 3 arguments:
    http://docs.celeryproject.org/en/latest/userguide/canvas.html#chains

    Got an error when trying to define this as a class based task
    """
    data = {}
    data["failed_task"] = request.task
    data["exception"] = str(exc)
    data["traceback"] = traceback
    data["ain"] = ain

    logger.info(f"Sending error data: {data} to {callback_url}")


#
# Flask Routes
#
@app.route("/process", methods=["POST", "GET"])
def process():
    ain = request.args.get("ain")
    callback_url = request.args.get("callback_url")

    # we create a task id for the outer task so that inner tasks can update its
    # state
    task_id = str(uuid4())

    result = chain(
        call.s(ain, outer_task_id=task_id).set(
            link_error=send_error.s(ain, callback_url)
        ),
        get_recording_uri.s(outer_task_id=task_id).set(
            countdown=60,  # delay getting the recording as the call takes time
            link_error=send_error.s(ain, callback_url),
        ),
        transcribe.s(outer_task_id=task_id).set(
            link_error=send_error.s(ain, callback_url)
        ),
        extract_info.s(outer_task_id=task_id).set(
            link_error=send_error.s(ain, callback_url)
        ),
        send_result.s(ain, callback_url, outer_task_id=task_id),
    ).apply_async(task_id=task_id)

    return jsonify(
        {
            "id": result.id,
            "ain": ain,
            "task_id": result.task_id,
            "status": result.status,
            "state": result.state,
        }
    )


@app.route("/status/<task_id>")
def status(task_id):
    result = AsyncResult(task_id)

    return jsonify(
        {"task_id": result.task_id, "status": result.status, "state": result.state}
    )
