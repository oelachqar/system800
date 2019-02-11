class State(object):
    """
    These are the status in order for a single run.
    """

    new = "new"
    calling = "calling"
    recording_ready = "recording_ready"
    transcribing = "transcribing_recording"
    transcribing_failed = "transcribing_failed"
    transcribing_done = "transcribing_completed"
    extracting = "extracting_info"
    extracting_done = "extracting_done"
    error = "error"
    user_error = "user_error"
    user_not_authorized = "user_not_authorized"
    failed_to_return_info = "failed_to_return_info"
