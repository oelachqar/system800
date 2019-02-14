import re

from uszipcode import SearchEngine as ZipcodeSearchEngine

from workflow.extract.utils import states_abbrev_lowercase


def get_re_for_location_parsing():
    states_or = "|".join(states_abbrev_lowercase.keys())
    return r"({states_or})".format(**locals()) + r" (\d{5})"


def find_possible_locations(s):
    q = get_re_for_location_parsing()
    return list(set(re.findall("(?i)" + q, s)))


def extract_location(s):
    """ Examples:
    'something something in Seattle Washington 98102'
    -> {'State': 'WA',
        'City':'Seattle',
        'Zipcode':'98102',
        'Confidence_location':'high'}

    'here the zip code does not match the state somecity texas 10983'
    -> {'State': 'TX', '
        City': None,
        'Zipcode': '10983',
        'Confidence_location': 'low'}
    """
    z_search = ZipcodeSearchEngine()
    possible_locations = find_possible_locations(s)
    keys = ["State", "City", "Zipcode"]
    for state, zipcode in possible_locations:
        zip_info = z_search.by_zipcode(zipcode)
        if states_abbrev_lowercase[state.lower()] == zip_info.state:
            d = {key: getattr(zip_info, key.lower()) for key in keys}
            d["Confidence_location"] = "high"
            return d
    if possible_locations != []:
        d = {
            "State": states_abbrev_lowercase[possible_locations[0][0].lower()],
            "City": None,
            "Zipcode": possible_locations[0][1],
            "Confidence_location": "low",
        }
        return d
    else:
        return {
            "State": None,
            "City": None,
            "Zipcode": None,
            "Confidence_location": None,
        }
