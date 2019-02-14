import base64
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
    call_final_pause_secs = os.getenv("CALL_FINAL_PAUSE", 45)
    call_initial_pause_secs = os.getenv("CALL_INITIAL_PAUSE", 0)

    # tokens
    token_secret_key = os.getenv("TOKEN_SECRET_KEY")
    token_expiration_seconds = int(os.getenv("TOKEN_EXPIRATION_SECONDS", 300))
    token_sign_algorithm = os.getenv("TOKEN_SIGN_ALGORITHM", "HS256")

    # speech to text config
    google_credentials_json = base64.urlsafe_b64decode(
        os.getenv("GOOGLE_CREDENTIALS_JSON").encode("utf8")
    ).decode("utf8")

    # celery config
    celery_broker = os.getenv("CELERY_BROKER_URL")
    celery_result_backend = os.getenv("CELERY_RESULT_BACKEND")
    celery_timezone = "UTC"

    # auth temporary
    auth_user = os.getenv("AUTH_USER")
    auth_password_hash = os.getenv("AUTH_PASSWORD_HASH")


class TestConfig(Config):
    # call testing
    test_call_case_number = os.getenv("TEST_CALL_CASE_NUMBER")
    test_call_recording_file = os.getenv("TEST_CALL_RECORDING_FILE")

    # speech to text testing
    test_google_audio_path = os.getenv("TEST_GOOGLE_AUDIO_PATH")
