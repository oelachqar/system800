import os

from dotenv import load_dotenv

# load environment variables from .env, without overriding any existing ones
load_dotenv(override=False)


class Config(object):
    # tts config
    google_credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")


class TestConfig(Config):
    # tts testing
    test_google_audio_path = os.getenv("TEST_GOOGLE_AUDIO_PATH")
