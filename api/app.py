import datetime
import json
import requests
from uuid import uuid4

from celery import chain, group
from celery.result import AsyncResult
from flask import Flask, g, jsonify, request
from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth
import jwt
from werkzeug.security import check_password_hash

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
from api.validate_input import validate_ain, validate_callback_url
from config import Config


#
# Init apps
#
app = Flask(__name__)
app.config.update(
    CELERY_BROKER_URL=Config.celery_broker,
    CELERY_RESULT_BACKEND=Config.celery_result_backend,
    CELERY_TIMEZONE=Config.celery_timezone,
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

    data["ain"] = ain

    # Return the outer id (same that we returned initially).
    # We assume here that all tasks using this error handler take outer_task_id
    # as a keyword argument.
    task_id = request.kwargs.get("outer_task_id", "")
    data["task_id"] = task_id

    # Retrieve any state and error message from the failing task.
    result = AsyncResult(task_id)

    data["state"] = result.state or ""

    # result.info is set by the "meta" argument to task.update_state
    if result.info is not None:
        msg = result.info.get("error_message", "")
        data["error_messege"] = msg
    else:
        data["error_message"] = ""

    logger.info(f"Sending error data: {data} to {callback_url}")

    requests.post(callback_url, json=data)


@celery.task()
def dummy_task(prev, ain, callback_url):
    """ So that we can an assign a task id to a workflow containing a group
    """

    logger.info(f"All tasks for ain: {ain}, callback_url: {callback_url} are done.")

    # prev contains the output of the two previous tasks, but the order is
    # not always as expected https://github.com/celery/celery/issues/3781.
    # However delete_recordings returns None
    return prev[0] if prev[0] else prev[1]


#
# Authentication
#
@basic_auth.verify_password
def verify_password(username, password):
    if username == Config.auth_user and check_password_hash(
        Config.auth_password_hash, password
    ):
        g.curent_user = {"has_access": True}
        return True

    return False


@basic_auth.error_handler
def basic_auth_error():
    msg = "Wrong username / password."
    response = jsonify({"state": State.user_not_authorized, "error_message": msg})
    response.status_code = 401
    return response


@token_auth.verify_token
def verify_token(token):
    if not token:
        return False

    try:
        payload = jwt.decode(
            token, Config.token_secret_key, algorithms=[Config.token_sign_algorithm]
        )
    except (jwt.DecodeError, jwt.ExpiredSignatureError):
        return False

    g.current_user = {"has_access": payload["has_access"]}
    return True


@token_auth.error_handler
def token_auth_error():
    msg = "The current user is not authenticated."
    response = jsonify({"state": State.user_not_authorized, "error_message": msg})
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
            "has_access": user["has_access"],
            "exp": datetime.datetime.utcnow()
            + datetime.timedelta(seconds=Config.token_expiration_seconds),
        },
        Config.token_secret_key,
        algorithm=Config.token_sign_algorithm,
    ).decode("utf-8")
    return jsonify({"token": token})


@app.route("/process", methods=["POST", "GET"])
@token_auth.login_required
def process():
    # check that the current user has enough privileges
    if not g.current_user["has_access"]:
        msg = "The current user is not authorized to make this request"
        response = jsonify({"state": State.user_not_authorized, "error_message": msg})
        response.status_code = 403
        return response

    ain = request.values.get("ain")

    # checks if ain is numeric and of the right length
    response = validate_ain(ain)
    if response != "valid":
        return response

    # AINs are 8 or 9 digit numbers.
    # If an 8 digit number is provided, a 0 must be pre-pended
    if len(ain) == 8:
        ain = "0" + ain

    callback_url = request.values.get("callback_url")

    # checks that callback_url is a valid url
    response = validate_callback_url(callback_url)
    if response != "valid":
        return response

    # we create a task id for the outer task so that inner tasks can update its
    # state
    task_id = str(uuid4())

    """
    Workflow:
    place_call* - check_call_done* - get_recording* - transcribe* - extract* - send
                                                         |                      |
                                                      delete_recording -----  dummy

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
        dummy_task.s(ain, callback_url),
    ).apply_async(task_id=task_id)

    return jsonify({"ain": ain, "task_id": result.task_id, "state": result.state})


@app.route("/status/<task_id>")
@token_auth.login_required
def status(task_id):
    result = AsyncResult(task_id)

    # result.info stores either the final result, intermediate metadata, or an exception
    data = result.info

    # ensure the data is json serialable (will fail for exceptions)
    try:
        json.dumps(data)
    except Exception:
        data = None

    return jsonify({"task_id": result.task_id, "state": result.state, "data": data})


@app.route("/debug_callback", methods=["POST"])
def debug_callback():
    if not request.is_json:
        return "", 400

    print(request.get_json())
    return "", 200
