import unittest

from config import TestConfig
from workflow.transcribe.azure_transcribe import AzureTranscriber


# @unittest.skip
class TestAzureTranscriber(unittest.TestCase):
    def setUp(self):
        self.azure_transcriber = AzureTranscriber(TestConfig.azure_speech_key)
        self.audio_path = TestConfig.test_google_audio_path

    def test_transcribe(self):
        transcript = self.azure_transcriber.transcribe_audio_file_path(self.audio_path)
        # self.assertEqual(transcript.strip(), self.expected_text)
        print(transcript)
        self.assertIsNotNone(transcript)


if __name__ == "__main__":
    unittest.main()
