import argparse
import os
import requests

from workflow.call.place_call import TwilioCallWrapper
import unittest

from config import TestConfig


class CallURIHandler(object):
    def __init__(self, recording_file):
        self.recording_file = recording_file

    def call_done_callback(self, case_number, call_duration, recording_uri):
        print(f"Call duration: {call_duration}")

        response = requests.get(recording_uri)
        if response.status_code != 200:
            print(f"Could not retrieve recording from {recording_uri}")
            return

        if os.path.exists(self.recording_file):
            print(f"File {self.recording_file} exists")
            input("Press enter to continue...")

        print("Saving recording to {self.recording_file}")
        with open(self.recording_file, "wb") as f:
            f.write(response.content)


def main(case_number, recording_file):
    print(f"Making call for case number: {case_number}")
    print("Come back in 90 secs...")
    call_uri_handler = CallURIHandler(recording_file)

    call_wrapper = TwilioCallWrapper(
        twilio_account_sid=TestConfig.twilio_account_sid,
        twilio_auth_token=TestConfig.twilio_auth_token,
        to_phone=TestConfig.to_phone,
        from_phone=TestConfig.from_phone,
        call_placed_callback=None,
        call_done_callback=call_uri_handler.call_done_callback,
    )

    call_wrapper.place_call(case_number)


if __name__ == "__main__":
    description = "Makes call for a single case number and saves recording to given file"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--file", help="File to save recording", type=str, required=True)
    parser.add_argument("--number", help="Case number", type=int, required=True)
    parser.add_argument("--to_phone", help="the court number", default="+18008675309")
    parser.add_argument(
        "--from_phone", help="number you have registered with Twilio", default="+18008675309"
    )

    args = parser.parse_args()

    main(args.number, args.file)
