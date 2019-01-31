import time
from flask import Flask, flash, render_template, request, jsonify
from celery import chain
from celery.exceptions import MaxRetriesExceededError
from celery.result import AsyncResult

from .celery_app import make_celery

from config import Config
from workflow.call.twilio_call_wrapper import (
    TwilioCallWrapper,
    TwilioRecordingURIResponseStatus,
)
from workflow.transcribe.google_tts import GoogleTranscriber

#
# Init apps
#
app = Flask(__name__)
app.config.update(
    CELERY_BROKER_URL=Config.celery_broker,
    CELERY_RESULT_BACKEND=Config.celery_result_backend,
)
celery = make_celery(app, name="app")

twilio = TwilioCallWrapper(
    Config.call_twilio_account_sid,
    Config.call_twilio_auth_token,
    Config.call_max_length_secs,
    Config.call_number_to_call,
    Config.call_twilio_local_number,
)

tts = GoogleTranscriber(
    Config.google_credentials_json, None
)  # preferred phrases None for now


#
# Flask Routes
#
@app.route("/process", methods=["POST"])
def process():
    ain = request.args.get("ain")
    result = chain(
        call.s("https://blah", ain),
        get_recording_uri.s(),
        transcribe.s(),
        extract_info.s(),
        send_result.s(),
    )()
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


#
# Celery Tasks
#

# TODO:
# - rate limit this task globally (I think Twilio will limit to 1 call
#   per second anyway, but we may want a lower rate)
@celery.task()
def call(callback_url, ain):
    print(f"Call task got ain = {ain}, callback_url = {callback_url}")

    call_sid = twilio.place_and_record_call(ain)

    print(f"Call scheduled, call_sid = {call_sid}")

    return callback_url, call_sid


# TODO:
# - add sensible values for max retries and delay to config
# - add a backoff
# - remove asserts
# - error logging
@celery.task(bind=True, max_retries=10)
def get_recording_uri(self, callback_url_and_call_sid):
    callback_url, call_sid = callback_url_and_call_sid
    print(f"Recording uri task  got callback_url = {callback_url}, call_sid = {call_sid}.")

    status, recording_uri = twilio.try_fetch_full_recording_uri(call_sid)

    if status == TwilioRecordingURIResponseStatus.error:
        assert recording_uri == ""
        return callback_url, recording_uri

    if (
        status == TwilioRecordingURIResponseStatus.call_queued
        or status == TwilioRecordingURIResponseStatus.call_in_progress
    ):
        try:
            print(f"Status of call {call_sid} is \"{status}\": trying again")
            self.retry(countdown=10)
        except MaxRetriesExceededError:
            print(f"Exceeded max retries, giving up")
            # clean up
            twilio.delete_call(call_sid)

            assert recording_uri == ""
            return callback_url, recording_uri

    # clean up
    twilio.delete_call(call_sid)

    print(f"Got recording_uri = {recording_uri}")

    assert status == TwilioRecordingURIResponseStatus.success
    return callback_url, recording_uri


@celery.task()
def transcribe(callback_url_and_recording_uri):
    callback_url, recording_uri = callback_url_and_recording_uri
    print(f"Transcribe task got callback_url = {callback_url}, recording_uri = {recording_uri}.")

    text = ""

    if recording_uri == "":
        print("Got no recording_uri")
        return callback_url, text

    text, status = tts.transcribe_audio_at_uri(recording_uri)

    print(f"Status = {status}")
    print(f"Transcript = {text}")

    return callback_url, text


@celery.task()
def extract_info(callback_url_and_text):
    callback_url, text = callback_url_and_text
    print(f"Extract got callback_url = {callback_url}, text = {text}.")
    time.sleep(1)
    print("Extract done")
    return "data"


@celery.task()
def send_result(data):
    print(f"Sending data {data}.")
    time.sleep(1)
    print(f"Sending data {data} done.")
    return "data"
