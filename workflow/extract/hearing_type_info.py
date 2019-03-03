def extract_hearing_type(s):
    """ Examples:
    'Your next individual hearing date is December 13th ...'
    -> {"HearingType": "individual"}

    'Your next master hearing date is December 13th ...'
    -> {"HearingType": "master"}

    '... does not match any record in the system"
    -> {"HearingType": None}

    """
    s = s.lower()
    hearingType = "HearingType"
    master = "master"
    individual = "individual"

    # adding stronger conditions first to avoid false positives
    if "next individual hearing" in s:
        return {hearingType: individual}
    elif "next master hearing" in s:
        return {hearingType: master}
    elif "individual" in s:
        return {hearingType: individual}
    elif "master" in s:
        return {hearingType: master}
    else:
        return {hearingType: None}
