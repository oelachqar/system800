from urllib.parse import urlparse
from api.state import State
from flask import jsonify


def validate_ain(ain):
    if not ain:
        msg = "null or empty ain"
        response = jsonify({"state": State.user_error, "error_message": msg})
        response.status_code = 400
        return response

    if not ain.isdigit():
        msg = "empty ain"
        response = jsonify({"state": State.user_error, "error_message": msg})
        response.status_code = 400
        return response

    # immediately fail if ain is not of the right length
    if len(ain) != 9 and len(ain) != 8:
        msg = "ain is wrong length"
        response = jsonify({"state": State.user_error, "error_message": msg})
        response.status_code = 400
        return response

    return "valid"


def validate_callback_url(callback_url):
    # check callback url not null or empty
    if not callback_url:
        response = jsonify(
            {"state": State.user_error, "error_message": "callback url null or empty"}
        )
        response.status_code = 400
        return response

    # check that callback url is a url
    parsed_url = urlparse(callback_url)
    if not bool(parsed_url.scheme):
        response = jsonify(
            {"state": State.user_error, "error_message": "callback url not valid"}
        )
        response.status_code = 400
        return response

    return "valid"
