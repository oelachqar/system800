class State(object):
    """
    These are the status in order for a single run.
    """

    new = "new"

    calling = "calling"
    calling_error = "calling_error"
    call_complete = "call_complete"

    recording_retrieval_error = "recording_retrieval_error"
    recording_ready = "recording_ready"

    transcribing = "transcribing_recording"
    transcribing_failed = "transcribing_failed"
    transcribing_done = "transcribing_completed"

    extracting = "extracting_info"
    extracting_done = "extracting_done"

    sending_to_callback_error = "sending_to_callback_error"
    sending_to_callback_done = "sending_to_callback_done"

    error = "error"
    user_error = "user_error"
    user_not_authorized = "user_not_authorized"
    failed_to_return_info = "failed_to_return_info"
