import time

from celery import Task
from celery.exceptions import MaxRetriesExceededError
from celery.utils.log import get_task_logger

from config import Config

from workflow.call.twilio_call_wrapper import (
    TwilioCallWrapper,
    TwilioRecordingURIResponseStatus,
)
from workflow.transcribe.google_tts import GoogleTranscriber

from .state import State

logger = get_task_logger("app")

twilio = TwilioCallWrapper(
    Config.call_twilio_account_sid,
    Config.call_twilio_auth_token,
    Config.call_initial_pause_secs,
    Config.call_final_pause_secs,
    Config.call_number_to_call,
    Config.call_twilio_local_number,
)

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

    def run(self, ain):
        logger.info(f"Call task got ain = {ain}")

        self.update_state(state=State.calling)

        call_sid = twilio.place_and_record_call(ain)

        logger.info(f"Call scheduled, call_sid = {call_sid}")

        return call_sid


class PullRecording(Task):
    """ Retrieves the recording uri from a call sid once the call has completed.
    """

    max_retries = 10
    retry_backoff = 10
    retry_jitter = True
    track_started = True

    def run(self, call_sid):
        logger.info(f"Recording uri task call_sid = {call_sid}.")

        status, recording_uri = twilio.try_fetch_full_recording_uri(call_sid)

        if status == TwilioRecordingURIResponseStatus.error:
            self.update_state(state=State.error)

            assert recording_uri == ""
            return recording_uri

        if (
            status == TwilioRecordingURIResponseStatus.call_queued
            or status == TwilioRecordingURIResponseStatus.call_in_progress
        ):
            try:
                logger.info(f'Status of call {call_sid} is "{status}": trying again')
                self.retry(countdown=10)
            except MaxRetriesExceededError:
                logger.info(f"Exceeded max retries, giving up")
                # clean up
                twilio.delete_call(call_sid)

                assert recording_uri == ""
                return recording_uri

        # clean up
        twilio.delete_call(call_sid)

        logger.info(f"Got recording_uri = {recording_uri}")
        self.update_state(state=State.recording_ready)

        assert status == TwilioRecordingURIResponseStatus.success
        return recording_uri


class TranscribeCall(Task):
    """ Returns a transcription of the audio at the given uri.
    """

    track_started = True

    def run(self, recording_uri):
        logger.info(f"Transcribe task got recording_uri = {recording_uri}.")

        text = ""

        if recording_uri == "":
            logger.info("Got no recording_uri")
            return text

        self.update_state(state=State.transcribing)

        text, status = tts.transcribe_audio_at_uri(recording_uri)

        logger.info(f"Status = {status}")
        logger.info(f"Transcript = {text}")
        self.update_state(state=State.transcribing_done)

        return text


class ExtractInfo(Task):
    track_started = True

    def run(self, text):
        logger.info(f"Extract got text = {text}.")
        self.update_state(state=State.extracting)
        time.sleep(1)
        logger.info("Extract done")
        self.update_state(state=State.extracting_done)
        return "data"


class SendResult(Task):
    track_started = True

    def run(self, callback_url, data):
        logger.info(f"Send task got callback_url = {callback_url}, data = {data}.")
        time.sleep(1)
        logger.info(f"Sending data {data} done.")
        return "data"
