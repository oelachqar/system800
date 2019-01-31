from celery import chain
from celery.result import AsyncResult

from config import Config

from flask import Flask, jsonify, request

from .celery_app import make_celery
from .tasks import ExtractInfo, InitiateCall, PullRecording, SendResult, TranscribeCall


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

#
# Flask Routes
#
@app.route("/process", methods=["POST", "GET"])
def process():
    ain = request.args.get("ain")
    callback_url = request.args.get("callback_url")

    result = chain(
        call.s(ain),
        get_recording_uri.s().set(
            countdown=60
        ),  # delay getting the recording as the call takes time
        transcribe.s(),
        extract_info.s(),
        send_result.s(callback_url),
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
