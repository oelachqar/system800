import time
from flask import Flask, flash, render_template, request, jsonify
from celery import chain
from celery.result import AsyncResult

from .celery_app import make_celery

from config import Config

#
# Init apps
#
app = Flask(__name__)
app.config.update(
    CELERY_BROKER_URL=Config.celery_broker,
    CELERY_RESULT_BACKEND=Config.celery_result_backend,
)
celery = make_celery(app, name="app")

#
# Flask Routes
#
@app.route("/process", methods=["POST"])
def process():
    ain = request.args.get("ain")
    result = chain(call.s(ain), transcribe.s(), extract_info.s(), send_result.s())()
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
@celery.task()
def call(ain):
    print(f"Calling {ain}.")
    time.sleep(1)
    print(f"Call {ain} done.")
    return "filename"


@celery.task()
def transcribe(audio_path):
    print(f"Transcribing {audio_path}.")
    time.sleep(1)
    print(f"Transcribing {audio_path} done.")
    return "text"


@celery.task()
def extract_info(text):
    print(f"Transcribing {extract_info}.")
    time.sleep(1)
    print(f"Transcribing {extract_info} done.")
    return "data"


@celery.task()
def send_result(data):
    print(f"Sending data {data}.")
    time.sleep(1)
    print(f"Sending data {data} done.")
    return "data"
