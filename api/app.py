from uuid import uuid4

from api.celery_app import make_celery
from api.tasks import (
    DeleteRecordings,
    ExtractInfo,
    InitiateCall,
    PullRecording,
    SendResult,
    TranscribeCall,
    logger,
)

from celery import chain, group
from celery.result import AsyncResult

from config import Config

from flask import Flask, jsonify, request

import requests


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
delete_recordings = celery.register_task(DeleteRecordings())


@celery.task()
def send_error(request, exc, traceback, ain, callback_url):
    """
    Inform caller of errors.
    Using the link_error example here which explains first 3 arguments:
    http://docs.celeryproject.org/en/latest/userguide/canvas.html#chains

    Got an error when trying to define this as a class based task
    """
    data = {}
    data["failed_task"] = request.task  # the celery task name
    data["exception"] = str(exc)
    data["traceback"] = traceback
    data["ain"] = ain
    # Return the outer id (same that we returned initially).
    # We assume here that all tasks using this error handler take outer_task_id
    # as a keyword argument.
    data["task_id"] = request.kwargs.get("outer_task_id", "")

    logger.info(f"Sending error data: {data} to {callback_url}")
    requests.post(callback_url, json=data)


@celery.task()
def dummy_task(ain, callback_url, outer_task_id):
    """ So that we can an assign a task id to a workflow containing a group
    """
    logger.info(
        f"All tasks for ain: {ain}, callback_url: {callback_url}, "
        f"task_id: {outer_task_id} done."
    )
    return None


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

    """
    Workflow:
    schedule_call* -- check_call_done* -- transcribe* -- extract* -- send
                                               |                      |
                                          delete_recording  -------  dummy

    *: after failure, we invoke send_error to inform caller of error
    """

    # TODO
    # add extra error handlers to ensure recordings deleted if get_recording_uri
    # or transcribe fail

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
        group(
            chain(
                extract_info.s(outer_task_id=task_id).set(
                    link_error=send_error.s(ain, callback_url)
                ),
                send_result.s(ain, callback_url, outer_task_id=task_id),
            ),
            delete_recordings.s(),
        ),
        dummy_task.si(ain, callback_url, outer_task_id=task_id),
    ).apply_async(task_id=task_id)

    return jsonify(
        {
            "ain": ain,
            "task_id": result.task_id,
            "state": result.state,
        }
    )


@app.route("/status/<task_id>")
def status(task_id):
    result = AsyncResult(task_id)

    return jsonify(
        {"task_id": result.task_id, "state": result.state}
    )


@app.route("/debug_callback", methods=['POST'])
def debug_callback():
    if not request.is_json:
        return '', 400

    print(request.get_json())
    return '', 200
