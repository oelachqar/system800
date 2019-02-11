import io

import requests

import speech_recognition as sr

from workflow.transcribe import exceptions


class GoogleTranscriber(object):
    def __init__(self, google_credentials_json, google_preferred_phrases):
        self.google_creds = google_credentials_json
        self.language = "en-US"
        self.preferred_phrases = google_preferred_phrases

    def transcribe_audio_file_path(self, audio_file_path):
        """ Transcribe the audio at the given location.

        audio_file_path: may be a filename or a file object
        https://github.com/Uberi/speech_recognition/blob/master/reference/library-reference.rst#audiofilefilename_or_fileobject-unionstr-ioiobase---audiofile
        """

        with sr.AudioFile(audio_file_path) as source:
            r = sr.Recognizer()
            audio_object = r.record(source)
            try:
                # hitting this error with SpeechRecognition module if preferred
                # phrases is not None
                # https://github.com/Uberi/speech_recognition/issues/334
                transcript = r.recognize_google_cloud(
                    audio_data=audio_object,
                    credentials_json=self.google_creds,
                    language=self.language,
                    # preferred_phrases=self.preferred_phrases,
                    preferred_phrases=None,
                    show_all=False,
                )

                return transcript

            except sr.UnknownValueError as exc:
                raise exceptions.BadAudio(
                    "Speech to text audio unintelligible"
                ) from exc

            except sr.RequestError as exc:
                raise exceptions.RequestError("Speech to text request failed") from exc

    def transcribe_audio_at_uri(self, audio_uri):
        try:
            response = requests.get(audio_uri)
            response.raise_for_status()

        # http://docs.python-requests.org/en/latest/user/quickstart/#errors-and-exceptions
        except requests.exceptions.RequestException as exc:
            raise exceptions.RequestError(
                f"Error retrieving audio from uri: {audio_uri}"
            ) from exc

        audio = io.BytesIO(response.content)

        return self.transcribe_audio_file_path(audio)
