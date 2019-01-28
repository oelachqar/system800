import os

from dotenv import load_dotenv

# load environment variables from .env, without overriding any existing ones
load_dotenv(override=False)


class Config(object):
    # tts config
    google_credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

    # call config
    twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    to_phone = "+18008675309"
    from_phone = "+18008675309"


class TestConfig(Config):
    # tts testing
    test_google_audio_path = os.getenv("TEST_GOOGLE_AUDIO_PATH")
