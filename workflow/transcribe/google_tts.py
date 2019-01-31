import io
import requests
import sys
import speech_recognition as sr

from .tts_status import TranscriptionStatus


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
        r = sr.Recognizer()
        transcript = ""
        transcription_status = TranscriptionStatus.success
        with sr.AudioFile(audio_file_path) as source:
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
            except sr.UnknownValueError as e:
                transcription_status = TranscriptionStatus.transcription_error
                print("Google Cloud Speech could not understand audio: {0}".format(e))
            except sr.RequestError as e:
                transcription_status = TranscriptionStatus.request_error
                print(
                    "Could not request results from Google Cloud Speech " "service; {0}".format(e)
                )
            except Exception:
                print("Unknown transcription error:", sys.exc_info())
                transcription_status = TranscriptionStatus.unknown_error
        return transcript, transcription_status

    # TODO
    # deal with exceptions
    def transcribe_audio_at_uri(self, audio_uri):
        response = requests.get(audio_uri)

        audio = io.BytesIO(response.content)

        return self.transcribe_audio_file_path(audio)
