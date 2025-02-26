import random
import requests
from requests.exceptions import RequestException

from celery import Task
from celery.exceptions import MaxRetriesExceededError
from celery.utils.log import get_task_logger
from twilio.rest.api.v2010.account.call import CallInstance

from api.state import State
from config import Config
from workflow.call import exceptions as CallExceptions
from workflow.call.twilio_call_wrapper import TwilioCallWrapper
from workflow.extract import date_info, location_info
from workflow.transcribe import exceptions as TranscribeExceptions
from workflow.transcribe.google_transcribe import GoogleTranscriber


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

transcriber = GoogleTranscriber(
    Config.google_credentials_json, None
)  # preferred phrases None for now


def get_countdown(retry_backoff, current_retries, retry_jitter, retry_backoff_max):
    # class variables below don't work for self.retry()
    # https://stackoverflow.com/questions/9731435/retry-celery-tasks-with-exponential-back-off#comment90534054_46467851

    # Following:
    # https://stackoverflow.com/a/9752811
    # https://celery.readthedocs.io/en/latest/userguide/tasks.html#Task.retry_backoff

    result = min(retry_backoff_max, retry_backoff * (2 ** current_retries))

    if retry_jitter:
        result += int(random.uniform(0, result / 4.0))

    return result


class InitiateCall(Task):
    """
        Schedules a call and returns the call sid.
        This task is rate limited to 1 request per second because of twilio limitations.
    """

    rate_limit = "1/s"

    max_retries = 10
    retry_backoff = 30
    retry_jitter = True
    retry_backoff_max = 600

    track_started = True

    default_error_message = "Error placing call"

    def run(self, ain, *, outer_task_id):
        try:
            logger.info(f"Call task got ain = {ain}")

            self.update_state(task_id=outer_task_id, state=State.calling)

            call_sid = twilio.place_and_record_call(ain)

            logger.info(f"Call scheduled, call_sid = {call_sid}")

            return call_sid

        except RequestException:
            # we retry on request exceptions up to max retries
            try:
                countdown = get_countdown(
                    self.retry_backoff,
                    self.request.retries,
                    self.retry_jitter,
                    self.retry_backoff_max,
                )
                self.retry(countdown=countdown)

            except MaxRetriesExceededError:
                self.update_state(
                    task_id=outer_task_id,
                    state=State.calling_error,
                    meta={"error_message": self.default_error_message},
                )
                raise

        except Exception:
            self.update_state(
                task_id=outer_task_id,
                state=State.calling_error,
                meta={"error_message": self.default_error_message},
            )
            raise


class CheckCallProgress(Task):
    """ Retrieves the recording uri from a call sid once the call has completed.
    """

    max_retries = 10
    retry_backoff = 30
    retry_jitter = True
    retry_backoff_max = 600

    track_started = True

    default_error_message = "Error checking call completion"

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
        try:
            status = twilio.fetch_status(call_sid)
            logger.info(f'Status of call {call_sid} is "{status}"')

            if status in self.in_progress_call_states:
                raise CallExceptions.CallInProgress

            if status in self.failed_call_states:
                logger.error(f'Failed call status: "{status}"')
                raise CallExceptions.CallFailed

            if status != TwilioCallStatus.COMPLETED:
                # treat unexpected status as an error
                logger.error(f'Unexpected call status: "{status}"')
                raise CallExceptions.UnknownError

            # the call has completed if we got this far
            self.update_state(task_id=outer_task_id, state=State.call_complete)
            return call_sid

        except (CallExceptions.CallInProgress, RequestException):
            # we retry if call in progress, or on request exceptions up to max retries
            try:
                countdown = get_countdown(
                    self.retry_backoff,
                    self.request.retries,
                    self.retry_jitter,
                    self.retry_backoff_max,
                )
                self.retry(countdown=countdown)

            except MaxRetriesExceededError:
                self.update_state(
                    task_id=outer_task_id,
                    state=State.calling_error,
                    meta={"error_message": self.default_error_message},
                )
                raise

        except Exception:
            self.update_state(
                task_id=outer_task_id,
                state=State.calling_error,
                meta={"error_message": self.default_error_message},
            )
            raise


class PullRecording(Task):

    max_retries = 10
    retry_backoff = 30
    retry_jitter = True
    retry_backoff_max = 600

    track_started = True

    default_error_message = "Error retrieving call recording"

    def run(self, call_sid, *, outer_task_id):
        # call has completed, find the recording uri
        try:
            recordings = twilio.fetch_recordings(call_sid)

            if not recordings or len(recordings) == 0:
                logger.error(f"Call {call_sid} completed with no recording")

                raise CallExceptions.NoRecording

            recording_uri = twilio.get_full_recording_uri(recordings[0])

            logger.info(f"Got recording_uri = {recording_uri}")

            self.update_state(task_id=outer_task_id, state=State.recording_ready)

            return {"call_sid": call_sid, "recording_uri": recording_uri}

        except RequestException:
            # we retry on request exceptions up to max retries
            try:
                countdown = get_countdown(
                    self.retry_backoff,
                    self.request.retries,
                    self.retry_jitter,
                    self.retry_backoff_max,
                )
                self.retry(countdown=countdown)

            except MaxRetriesExceededError:
                self.update_state(
                    task_id=outer_task_id,
                    state=State.recording_retrieval_error,
                    meta={"error_message": self.default_error_message},
                )
                raise

        except Exception:
            self.update_state(
                task_id=outer_task_id,
                state=State.recording_retrieval_error,
                meta={"error_message": self.default_error_message},
            )
            raise


class DeleteRecordings(Task):
    """ Deletes all recordings associated to a given call sid.
    """

    max_retries = 10
    retry_backoff = 30
    retry_jitter = True
    retry_backoff_max = 600

    def run(self, request):
        # We attempt to delete all recordings for the given call, and we return
        # the given data as the overall result for the chain.

        call_sid = request.get("call_sid")
        data = request.get("data")

        try:
            logger.info(f"Delete recordings task got call_sid = {call_sid}.")

            call = twilio.fetch_call(call_sid)

            for recording in call.recordings.list():
                recording.delete()

            return data

        # We retry on request exceptions up to max retries, and for other exceptions
        # we don't re-raise
        except RequestException:
            try:
                countdown = get_countdown(
                    self.retry_backoff,
                    self.request.retries,
                    self.retry_jitter,
                    self.retry_backoff_max,
                )
                self.retry(countdown=countdown)

            except MaxRetriesExceededError:
                logger.error(f"Failed to delete recordings for call {call_sid}")
                return data

        except Exception:
            logger.error(f"Failed to delete recordings for call {call_sid}")
            return data


class TranscribeCall(Task):
    """ Returns a transcription of the audio at the given uri.
    """

    # TODO
    # Ensure we only send < 1 min of audio to be transcribed -- otherwise we
    # need to make an async call to the speech to text service
    # (and not use speech rec package).

    track_started = True
    retry_backoff = 4
    retry_backoff_max = 300
    retry_jitter = True

    max_retries = 5

    def run(self, request, *, outer_task_id):
        try:
            call_sid = request.get("call_sid")
            recording_uri = request.get("recording_uri")

            self.update_state(task_id=outer_task_id, state=State.transcribing)

            text = transcriber.transcribe_audio_at_uri(recording_uri)

            logger.info(f"Transcript = {text}")

            self.update_state(task_id=outer_task_id, state=State.transcribing_done)

            return {"call_sid": call_sid, "text": text}

        except TranscribeExceptions.RequestError:
            # we retry on request errors
            try:
                countdown = get_countdown(
                    self.retry_backoff,
                    self.request.retries,
                    self.retry_jitter,
                    self.retry_backoff_max,
                )
                self.retry(countdown=countdown)

            except MaxRetriesExceededError:
                self.update_state(
                    task_id=outer_task_id, state=State.transcribing_failed
                )
                raise

        except Exception:
            # for other errors (unintelligible audio etc) we don't retry
            self.update_state(task_id=outer_task_id, state=State.transcribing_failed)
            raise


class ExtractInfo(Task):
    track_started = True

    def run(self, request, *, outer_task_id):
        """
        returns dictionary with transcription text and keys relating to extracted date
        and location info.
        all key values (except transcription text) are None if extraction fails
        """

        text = request.get("text")
        call_sid = request.get("call_sid")

        logger.info(f"Extract got text = {text}.")
        self.update_state(task_id=outer_task_id, state=State.extracting)

        d = {"trancription": text}

        date = date_info.extract_date_time(text)
        d.update(date)

        location = location_info.extract_location(text)
        d.update(location)

        logger.info(f"Date = {date}. Location = {location}")
        self.update_state(task_id=outer_task_id, state=State.extracting_done)

        return {"call_sid": call_sid, "data": d}


class SendResult(Task):

    max_retries = 10
    retry_backoff = 30
    retry_jitter = True
    retry_backoff_max = 600

    default_error_message = "Sending data to callback url failed"

    track_started = True

    def run(self, request, ain, callback_url, *, outer_task_id):
        try:
            data = request.get("data")

            logger.info(
                f"Send task got ain = {ain}, callback_url = {callback_url}, "
                f"data = {data}."
            )
            requests.post(callback_url, json=data)

            self.update_state(
                task_id=outer_task_id, state=State.sending_to_callback_done
            )

            return request

        except RequestException:
            # we retry on request errors
            try:
                countdown = get_countdown(
                    self.retry_backoff,
                    self.request.retries,
                    self.retry_jitter,
                    self.retry_backoff_max,
                )
                self.retry(countdown=countdown)

            except MaxRetriesExceededError:
                self.update_state(
                    task_id=outer_task_id,
                    state=State.sending_to_callback_error,
                    meta={"error_message": self.default_error_message, "data": data},
                )
                raise

        except Exception:
            self.update_state(
                task_id=outer_task_id,
                state=State.sending_to_callback_error,
                meta={"error_message": self.default_error_message, "data": data},
            )
            raise
