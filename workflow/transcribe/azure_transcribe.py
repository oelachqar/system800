import time

import azure.cognitiveservices.speech as speechsdk

from workflow.transcribe import exceptions


class AzureTranscriber(object):
    """
    Wrapper for the Azure speech to text service.
    See
    https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/quickstart-python
    and
    https://github.com/Azure-Samples/cognitive-services-speech-sdk/blob/master/samples/python/console/speech_sample.py
    """

    def __init__(self, azure_speech_key):
        self.speech_config = speechsdk.SpeechConfig(
            subscription=azure_speech_key,
            region="westus",
            speech_recognition_language="en-US"
        )

    def transcribe_audio_file_path(self, audio_file_path):
        # For now supports wav, not mp3
        # https://stackoverflow.com/questions/51614216/what-audio-formats-are-supported-by-azure-cognitive-services-speech-service-ss?rq=1
        audio_config = speechsdk.AudioConfig(
            use_default_microphone=False, filename=audio_file_path
        )
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config, audio_config=audio_config
        )

        done = False
        transcript = ""
        cancellation_details = None

        def stop_cb(evt):
            """callback that stops continuous recognition upon receiving an event `evt`"""
            print("CLOSING on {}".format(evt))
            speech_recognizer.stop_continuous_recognition()
            nonlocal done
            done = True

        def return_transcript(evt):
            """recognition is continuous, that is every sentence gets recognized separately.
            We want to concatenate all the sentences and return the full transcript"""
            nonlocal transcript
            transcript += " "
            transcript += evt.result.text

        def return_cancellation_details(evt):
            """return cancellation details"""
            nonlocal cancellation_details
            cancellation_details = evt.result.cancellation_details.error_details

        # Connect callbacks to the events fired by the speech recognizer
        speech_recognizer.recognized.connect(return_transcript)
        speech_recognizer.canceled.connect(return_cancellation_details)
        # stop continuous recognition on either session stopped or canceled events
        speech_recognizer.session_stopped.connect(stop_cb)
        speech_recognizer.canceled.connect(stop_cb)

        # Start continuous speech recognition
        speech_recognizer.start_continuous_recognition()

        while not done:
            time.sleep(0.5)

        if cancellation_details:
            raise exceptions.Canceled(
                "Azure Speech cancellation error: " + cancellation_details
                )
        if transcript == "":
            raise exceptions.BlankTranscript(
                "Azure Speech returned blank transcript"
            )

        return transcript
