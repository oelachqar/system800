import argparse
import os
import requests
import time
import unittest

from config import TestConfig

from workflow.call.twilio_call_wrapper import TwilioCallWrapper


def save_recording(recording_uri, recording_file):

    response = requests.get(recording_uri)
    if response.status_code != 200:
        print(f"Could not retrieve recording from {recording_uri}")
        return

    if os.path.exists(recording_file):
        print("File {0} exists".format(recording_file))
        input("Press enter to continue...")

    print("Saving recording to {0}".format(recording_file))
    with open(recording_file, "wb") as f:
        f.write(response.content)


def main(case_number, recording_file):
    twilio = TwilioCallWrapper(
        TestConfig.call_twilio_account_sid,
        TestConfig.call_twilio_auth_token,
        TestConfig.call_initial_pause_secs,
        TestConfig.call_final_pause_secs,
        TestConfig.call_number_to_call,
        TestConfig.call_twilio_local_number,
    )

    print(f"Making call for case number: {case_number}")
    print(f"Call will take {twilio.call_initial_pause_secs} seconds before digits are entered")
    print(f"Call will take {twilio.call_final_pause_secs} seconds after digits are entered")

    call_sid = twilio.place_and_record_call(case_number)

    call_status = twilio.fetch_status(call_sid)

    start = time.time()
    while call_status != "completed":
        call_status = twilio.fetch_status(call_sid)
        elapsed = time.time() - start
        print(f"Time elapsed = {elapsed}, call status = {call_status}")
        time.sleep(10)

    recordings = twilio.fetch_recordings(call_sid)
    print(f"Found {len(recordings)} recordings.")

    assert len(recordings) == 1, "Expect a single recording"

    recording_uri = twilio.get_full_recording_uri(recordings[0])

    save_recording(recording_uri, recording_file)

    print("Deleting recording and call from twilio")
    twilio.delete_recordings(call_sid)
    twilio.delete_call(call_sid)


@unittest.skip
class TestTwilioCallWrapper(unittest.TestCase):
    def test_make_and_record_call(self):
        main(TestConfig.test_call_case_number, TestConfig.test_call_recording_file)


if __name__ == "__main__":
    unittest.main()

    # description = "Makes call for a single case number and saves recording to given file"
    # parser = argparse.ArgumentParser(description=description)
    # parser.add_argument(
    #     '--file', help='File to save recording', type=str, required=True)
    # parser.add_argument('--number', help='Case number',
    #                     type=int, required=True)

    # args = parser.parse_args()

    # main(args.number, args.file)
