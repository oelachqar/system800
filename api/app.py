import requests
import time
from uuid import uuid4

from celery import chain, group
from celery.result import AsyncResult
from flask import Flask, g, jsonify, request
from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth
import jwt

from api.celery_app import make_celery
from api.state import State
from api.tasks import (
    CheckCallProgress,
    DeleteRecordings,
    ExtractInfo,
    InitiateCall,
    PullRecording,
    SendResult,
    TranscribeCall,
    logger,
)
from config import Config


#
# Init apps
#
app = Flask(__name__)
app.config.update(
    CELERY_BROKER_URL=Config.celery_broker,
    CELERY_RESULT_BACKEND=Config.celery_result_backend,
)

basic_auth = HTTPBasicAuth()
token_auth = HTTPTokenAuth()

celery = make_celery(app, name="app")

#
# Celery tasks
#
call = celery.register_task(InitiateCall())
get_recording_uri = celery.register_task(PullRecording())
check_call_progress = celery.register_task(CheckCallProgress())
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
# Authentication
#
@basic_auth.verify_password
def verify_password(username, password):
    # TODO implement a proper check
    g.curent_user = {"user_id": 123, "has_access": True}
    return True


@basic_auth.error_handler
def basic_auth_error():
    # TODO implement
    response = jsonify({})
    response.status_code = 401
    return response


@token_auth.verify_token
def verify_token(token):
    payload = jwt.decode(token, Config.token_secret_key, algorithms=["HS256"])
    g.current_user = {
        "user_id": payload["user_id"],
        "has_access": payload["has_access"],
    }
    return True


@token_auth.error_handler
def token_auth_error():
    # TODO implement
    response = jsonify({})
    response.status_code = 401
    return response


#
# Flask Routes
#
@app.route("/tokens", methods=["POST"])
@basic_auth.login_required
def get_token():
    user = g.curent_user
    token = jwt.encode(
        {
            "user_id": user["user_id"],
            "has_access": user["has_access"],
            "exp": time.time() + Config.token_expiration_seconds,
        },
        Config.token_secret_key,
        algorithm="HS256",
    ).decode("utf-8")
    return jsonify({"token": token})


@app.route("/process", methods=["POST", "GET"])
@token_auth.login_required
def process():
    # check that the current user has enough privileges
    if not g.current_user["has_access"]:
        return (
            jsonify(
                {
                    "state": State.user_not_authorized,
                    "error_message": "The current user is not authorized to make this request",
                }
            ),
            403,
        )

    ain = request.args.get("ain")

    # AINs are 8 or 9 digit numbers.
    # If an 8 digit number is provided, a 0 must be pre-pended
    if len(ain) == 8:
        ain = "0" + ain

    # immediately fail if ain is not of the right length
    if len(ain) != 9:
        return (
            jsonify(
                {"state": State.user_error, "error_message": "ain is wrong length"}
            ),
            400,
        )

    callback_url = request.args.get("callback_url")

    # check callback url is here
    try:
        response = requests.get(callback_url)
    except Exception as exc:
        return (
            jsonify(
                {
                    "state": State.user_error,
                    "error_message": "invalid callback url ",
                    "error": exc.__class__.__name__,
                }
            ),
            400,
        )
    if response.status_code >= 400:
        return (
            jsonify(
                {"state": State.user_error, "error_message": "invalid callback url "}
            ),
            400,
        )

    # we create a task id for the outer task so that inner tasks can update its
    # state
    task_id = str(uuid4())

    """
    Workflow:
    schedule_call* -- check_call_done* -- fetch_recording -- transcribe* -- extract* -- send
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
        check_call_progress.s(outer_task_id=task_id).set(
            countdown=60,  # delay the initial check as the call takes time
            link_error=send_error.s(ain, callback_url),
        ),
        get_recording_uri.s(outer_task_id=task_id).set(
            link_error=send_error.s(ain, callback_url)
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

    return jsonify({"ain": ain, "task_id": result.task_id, "state": result.state})


@app.route("/status/<task_id>")
@token_auth.login_required
def status(task_id):
    result = AsyncResult(task_id)

    return jsonify({"task_id": result.task_id, "state": result.state})


@app.route("/debug_callback", methods=["POST", "GET"])
def debug_callback():
    if request.method == "POST":
        if not request.is_json:
            return "", 400

        print(request.get_json())
        return "", 200
    elif request.method == "GET":
        return "", 200
