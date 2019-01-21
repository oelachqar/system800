import json
import os
import unittest

from workflow.transcribe.google_tts import GoogleTranscriber


class TestGoogleTranscriber(unittest.TestCase):
    def setUp(self):
        self.expected_text = "you are acting so weird and immature"

    def test_transcribe(self):
        google_transcriber = GoogleTranscriber(self.credentials_json, None)
        transcript = google_transcriber.transcribe_audio_file_path(self.audio_path)
        self.assertEqual(transcript[0].strip(), self.expected_text)

if __name__ == "__main__":
    TestGoogleTranscriber.audio_path = os.environ.get('TEST_GOOGLE_AUDIO_PATH')

    credentials_file = os.environ.get('TEST_GOOGLE_CREDENTIALS_FILE')
    with open(credentials_file, "r") as f:
        TestGoogleTranscriber.credentials_json = json.dumps(json.load(f))

    unittest.main()
