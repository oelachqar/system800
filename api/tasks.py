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
from workflow.transcribe.tts_status import TranscriptionStatus

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
            return call_sid, recording_uri

        if (
            status == TwilioRecordingURIResponseStatus.call_queued
            or status == TwilioRecordingURIResponseStatus.call_in_progress
        ):
            try:
                logger.info(f'Status of call {call_sid} is "{status}": trying again')
                self.retry(countdown=10)
            except MaxRetriesExceededError:
                logger.info(f"Exceeded max retries, giving up")

                assert recording_uri == ""
                return call_sid, recording_uri

        logger.info(f"Got recording_uri = {recording_uri}")
        self.update_state(state=State.recording_ready)

        assert status == TwilioRecordingURIResponseStatus.success
        return call_sid, recording_uri


# class DeleteRecordings(Task):
#     """ Deletes all recordings associated to a given call sid.
#     """

#     def run(self, call_sid):
#         logger.info(f"Delelte recordings task got call_sid = {call_sid}.")

#         call = twilio.fetch_call(call_sid)

#         for recording in call.recordings.list():
#             recording.delete()


class TranscribeCall(Task):
    """ Returns a transcription of the audio at the given uri.
    """

    track_started = True

    def run(self, call_sid_and_recording_uri):
        call_sid, recording_uri = call_sid_and_recording_uri
        logger.info(
            f"Transcribe task got call_sid = {call_sid}, recording_uri = {recording_uri}."
        )

        text = ""

        if recording_uri == "":
            logger.info("Got no recording_uri")

        else:
            self.update_state(state=State.transcribing)

            try:
                transcript, status = tts.transcribe_audio_at_uri(recording_uri)

                logger.info(f"Transcribe status = {status}")
                logger.info(f"Transcript = {transcript}")

                if status == TranscriptionStatus.success:
                    text = transcript
                    self.update_state(state=State.transcribing_done)

                else:
                    self.update_state(state=State.transcribing_failed)

            except Exception as err:
                logger.error(f"Transcription error: {err}")
                self.update_state(state=State.transcribing_failed)

        # ideally call DeleteRecordings above, not sure if that's possible
        # with class based tasks so doing it synchronously for now

        # finished with recording, so delete it from storage
        call = twilio.fetch_call(call_sid)
        for recording in call.recordings.list():
            recording.delete()

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
