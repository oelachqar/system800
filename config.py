import os

from dotenv import load_dotenv

# load environment variables from .env, without overriding any existing ones
load_dotenv(override=False)


class Config(object):
    # calling
    call_twilio_account_sid = os.getenv("CALL_TWILIO_ACCOUNT_SID")
    call_twilio_auth_token = os.getenv("CALL_TWILIO_AUTH_TOKEN")
    call_twilio_local_number = os.getenv("CALL_TWILIO_LOCAL_NUMBER")
    call_number_to_call = os.getenv("CALL_NUMBER_TO_CALL")
    call_max_length_secs = os.getenv("CALL_MAX_LENGTH_SECS") or 45

    # tts config
    google_credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")


class TestConfig(Config):
    # call testing
    test_call_case_number = os.getenv("TEST_CALL_CASE_NUMBER")
    test_call_recording_file = os.getenv("TEST_CALL_RECORDING_FILE")

    # tts testing


test_google_audio_path = os.getenv("TEST_GOOGLE_AUDIO_PATH")
