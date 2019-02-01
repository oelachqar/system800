"""
Place a Twilio phone call and record the outcome.
"""

import requests

from twilio.rest import Client as TwilioRestClient


class TwilioRecordingURIResponseStatus:
    """ Possible status when we try to retrieve a recording for a given call
    """
    success = "success"
    call_queued = "call_queued"
    call_in_progress = "call_in_progress"
    error = "error"


class TwilioCallWrapper(object):

    # use echo below to return whatever twiml is sent to it:
    # https://www.twilio.com/labs/twimlets/echo
    # we will specify the digits and length below
    # note: when specifying twim_url, replace '%7B' with '{' and '%7D' with '}'
    twiml_url = "http://twimlets.com/echo?Twiml=%3C%3Fxml%20version%3D%221.0%22%3F%3E%0A%3CResponse%3E%0A%3CPause%20length%3D%22{pauseBeforeSendingDigitsLength}%22%2F%3E%0A%3CPlay%20digits%3D%22{digits}%22%2F%3E%0A%3CPause%20length%3D%22{pauseAfterSendingDigitsLength}%22%2F%3E%0A%3CHangup%2F%3E%0A%0A%3C%2FResponse%3E&"

    # base is mentioned here: https://www.twilio.com/docs/voice/api/recording
    twilio_uri_base = "https://api.twilio.com"

    # api docs
    # https://www.twilio.com/docs/voice/api/call
    # https://www.twilio.com/docs/voice/api/recording

    def __init__(self, twilio_account_sid, twilio_auth_token, call_initial_pause_secs, call_final_pause_secs, number_to_call, twilio_local_number):
        self._client = TwilioRestClient(twilio_account_sid, twilio_auth_token)
        self.call_initial_pause_secs = call_initial_pause_secs
        self.call_final_pause_secs = call_final_pause_secs
        self.number_to_call = number_to_call
        self.twilio_local_number = twilio_local_number

    def try_callback_server(self):
        """ Sends a request to the twiml_url
        """
        try:
            response = requests.get(self.twiml_url)
            if response.status_code != 200:
                raise RuntimeError(
                    "Server {0} not found. Can't make calls.".format(self.twiml_url))
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Server {0} not found. Can't make calls.".format(self.twiml_url))

    def build_dtmf_sequence(self, case_number):
        """ Sequence represents the following:

        Send 1  [to enter in English?]
        Wait 1 Second
        Send case number
        Wait 1 Second
        Send 1  [why?]
        Wait 1 Second
        Send 1  [why?]
        Wait 1 Second
        Send 1  [why?]
        Wait for 10 seconds
        Send 1  [trick into a repeat so we catch the full message.]

        Note: sequence must be at most 32 digits long:
        https://www.twilio.com/docs/voice/api/call#create-a-call-resource
        (Can use <Play> in twiml instead)
        """

        # with repeat:
        # return "1ww{case_number}ww1ww1ww1".format(case_number=case_number) + ("w" * 5 * 2) + "1"

        # if warning of maintenance:
        # "1w1ww{case_number}ww1w1w1".format(case_number=case_number) + ("w" * 5 * 2) + "1"

        return "1ww{case_number}ww1ww1ww1".format(case_number=case_number)

    def place_and_record_call(self, case_number):
        """ Places a call which is recorded.

            Returns the call sid.
        """
        send_digits = self.build_dtmf_sequence(case_number)

        twiml_url = self.twiml_url.format(
            pauseBeforeSendingDigitsLength=self.call_initial_pause_secs,
            digits=send_digits,
            pauseAfterSendingDigitsLength=self.call_final_pause_secs)

        call = self._client.calls.create(
            to=self.number_to_call, from_=self.twilio_local_number, url=twiml_url, record=True)

        return call.sid

    def fetch_call(self, call_sid):
        """ Retrieves a call object from the call sid
        """
        return self._client.calls.get(call_sid).fetch()

    def hangup_call(self, call_sid):
        """ Ends a call if it is still in progress

            See: https://www.twilio.com/docs/voice/tutorials/how-to-modify-calls-in-progress-python
        """
        call = self.fetch_call(call_sid)
        if call.status != 'completed':
            call.update(status='completed')

    def delete_call(self, call_sid):
        """ Deletes the call with the given call sid
        """
        self.fetch_call(call_sid).delete()

    def fetch_status(self, call_sid):
        """ Get the status of the call with the given call sid
        """
        return self.fetch_call(call_sid).status

    def fetch_recordings(self, call_sid):
        """ Get list of recordings for given call sid
        """
        call = self.fetch_call(call_sid)
        return call.recordings.list()

    def delete_recordings(self, call_sid):
        """ Delete all recordings for given call sid
        """
        recordings = self.fetch_recordings(call_sid)
        for recording in recordings:
            recording.delete()

    def get_full_recording_uri(self, recording):
        """ Get the uri that can be used to download the given recording
        """
        return self._get_twilio_uri(recording.uri)

    def _get_twilio_uri(self, uri_from_recording):
        # recording.uri is:
        # -- relative to twilio_uri_base above, and
        # -- ends in ".json" which needs to be removed
        # https://www.twilio.com/docs/voice/api/recording#fetch-recording-metadata
        return self.twilio_uri_base + uri_from_recording.split(".json")[0]

    def try_fetch_full_recording_uri(self, call_sid):
        """ Returns a status and uri for the recording.
        The status is one of the members of TwilioRecordingURIResponseStatus.
        The uri is non-empty and valid only if the call has completed.
        """

        # we will return: status, recording_uri
        status = TwilioRecordingURIResponseStatus.error
        recording_uri = ""

        call_status = self.fetch_status(call_sid)

        if call_status == "queued":
            status = TwilioRecordingURIResponseStatus.call_queued

        elif call_status == "in-progress" or call_status == "ringing":
            status = TwilioRecordingURIResponseStatus.call_in_progress

        elif call_status == "completed":
            recordings = self.fetch_recordings(call_sid)
            if not recordings:
                status = TwilioRecordingURIResponseStatus.error
            else:
                status = TwilioRecordingURIResponseStatus.success
                recording_uri = self.get_full_recording_uri(recordings[0])

        # else:
        # nothing to do -- for any other call_status, we report an error
        # https://www.twilio.com/docs/voice/api/call

        return status, recording_uri
