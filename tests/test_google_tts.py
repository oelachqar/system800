import unittest

from config import TestConfig
from workflow.transcribe.google_tts import GoogleTranscriber


class TestGoogleTranscriber(unittest.TestCase):
    def setUp(self):
        self.google_transcriber = GoogleTranscriber(
            TestConfig.google_credentials_json, google_preferred_phrases=None)
        self.audio_path = TestConfig.test_google_audio_path
        self.expected_text = "you are acting so weird and immature"

    def test_transcribe(self):
        transcript = self.google_transcriber.transcribe_audio_file_path(
            self.audio_path)
        self.assertEqual(transcript[0].strip(), self.expected_text)


if __name__ == "__main__":
    unittest.main()
