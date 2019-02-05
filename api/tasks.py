from api.state import State

from celery import Task
from celery.exceptions import MaxRetriesExceededError
from celery.utils.log import get_task_logger

from config import Config

import requests

from twilio.rest.api.v2010.account.call import CallInstance

from workflow.call.twilio_call_wrapper import TwilioCallWrapper
from workflow.extract import date_info, location_info
from workflow.transcribe.google_tts import GoogleTranscriber
from workflow.transcribe import exceptions as TTSExceptions


logger = get_task_logger("app")

twilio = TwilioCallWrapper(
    Config.call_twilio_account_sid,
    Config.call_twilio_auth_token,
    Config.call_initial_pause_secs,
    Config.call_final_pause_secs,
    Config.call_number_to_call,
    Config.call_twilio_local_number,
)

TwilioCallStatus = CallInstance.Status

tts = GoogleTranscriber(
    Config.google_credentials_json, None
)  # preferred phrases None for now


class InitiateCall(Task):
    """
        Schedules a call and returns the call sid.
        This task is rate limited to 1 request per second because of twilio limitations.
    """

    rate_limit = "1/s"
    track_started = True

    def run(self, ain, *, outer_task_id):
        logger.info(f"Call task got ain = {ain}")

        self.update_state(task_id=outer_task_id, state=State.calling)

        call_sid = twilio.place_and_record_call(ain)

        logger.info(f"Call scheduled, call_sid = {call_sid}")

        return call_sid


class CheckCallProgress(Task):
    """ Retrieves the recording uri from a call sid once the call has completed.
    """

    max_retries = 10
    retry_backoff = 10
    retry_jitter = True
    track_started = True

    failed_call_states = [
        TwilioCallStatus.BUSY,
        TwilioCallStatus.FAILED,
        TwilioCallStatus.NO_ANSWER,
        TwilioCallStatus.CANCELED,
    ]

    in_progress_call_states = [
        TwilioCallStatus.QUEUED,
        TwilioCallStatus.RINGING,
        TwilioCallStatus.IN_PROGRESS,
    ]

    def run(self, call_sid, *, outer_task_id):
        status = twilio.fetch_status(call_sid)
        logger.info(f'Status of call {call_sid} is "{status}"')

        if status in self.in_progress_call_states:
            try:
                logger.info("Will retry")
                self.retry(countdown=10)

            except MaxRetriesExceededError:
                logger.info(f"Exceeded max retries, giving up")
                self.update_state(task_id=outer_task_id, state=State.error)
                return call_sid

        if status in self.failed_call_states:
            self.update_state(task_id=outer_task_id, state=State.error)
            logger.error(f'Error call status: "{status}"')
            return call_sid

        elif status == TwilioCallStatus.COMPLETED:
            self.update_state(task_id=outer_task_id, state=State.error)
            return call_sid

        else:
            # treat unexpected status as an error
            logger.error(f'Unexpected call status: "{status}"')
            self.update_state(task_id=outer_task_id, state=State.error)
            return call_sid


class PullRecording(Task):
    track_started = True

    def run(self, call_sid, *, outer_task_id):
        # call has completed, find the recording uri
        recordings = twilio.fetch_recordings(call_sid)
        recording_uri = ""
        if not recordings:
            logger.error(f"Call {call_sid} completed with no recording")

            self.update_state(task_id=outer_task_id, state=State.error)

            return {"call_sid": call_sid, "recording_uri": recording_uri}

        else:
            recording_uri = twilio.get_full_recording_uri(recordings[0])
            logger.info(f"Got recording_uri = {recording_uri}")

            self.update_state(task_id=outer_task_id, state=State.recording_ready)

            return {"call_sid": call_sid, "recording_uri": recording_uri}


class DeleteRecordings(Task):
    """ Deletes all recordings associated to a given call sid.
    """

    def run(self, request):
        call_sid = request.get("call_sid")
        logger.info(f"Delete recordings task got call_sid = {call_sid}.")

        call = twilio.fetch_call(call_sid)

        for recording in call.recordings.list():
            recording.delete()


class TranscribeCall(Task):
    """ Returns a transcription of the audio at the given uri.
    """

    # TODO
    # Ensure we only send < 1 min of audio to be transcribed -- otherwise we
    # need to make an async call to the tts service (and not use speech rec
    # package).

    track_started = True
    retry_backoff = 4
    retry_jitter = True
    max_retries = 5

    def run(self, request, *, outer_task_id):
        call_sid = request.get("call_sid")
        recording_uri = request.get("recording_uri")

        logger.info(
            f"Transcribe task got call_sid = {call_sid}, "
            f"recording_uri = {recording_uri}."
        )

        self.update_state(task_id=outer_task_id, state=State.transcribing)

        try:
            text = tts.transcribe_audio_at_uri(recording_uri)

            logger.info(f"Transcript = {text}")

            self.update_state(task_id=outer_task_id, state=State.transcribing_done)

            return {"call_sid": call_sid, "text": text}

        except TTSExceptions.RequestError as exc:
            # we retry on request errors
            raise self.retry(exc=exc)

        except Exception as exc:
            # for other errors (unintelligible audio etc) we don't retry
            logger.error(f"Transcription error: {exc}")

            self.update_state(task_id=outer_task_id, state=State.transcribing_failed)

            raise


class ExtractInfo(Task):
    track_started = True

    def run(self, request, *, outer_task_id):
        text = request.get("text")
        logger.info(f"Extract got text = {text}.")
        self.update_state(task_id=outer_task_id, state=State.extracting)
        d = {}
        # TODO: raise error if extraction fails ?
        date = date_info.extract_date_time(text)
        if date is not None:
            d.update(date)
        location = location_info.extract_location(text)
        if location is not None:
            d.update(location)
        logger.info(f"Date = {date}. Location = {location}")
        self.update_state(task_id=outer_task_id, state=State.extracting_done)
        return d


class SendResult(Task):
    track_started = True

    def run(self, data, ain, callback_url, *, outer_task_id):
        logger.info(
            f"Send task got ain = {ain}, callback_url = {callback_url}, data = {data}."
        )
        requests.post(callback_url, json=data)
        logger.info(f"Sending data {data} done.")
        return data
