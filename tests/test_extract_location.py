import unittest

from workflow.extract import location_info


class MyTest(unittest.TestCase):
    def test_isNotNone(self):
        self.assertIsNotNone(location_info.extract_location("Washington 98102"))

    def test_basic(self):
        self.assertEqual(
            location_info.extract_location("Washington 98102"),
            {"State": "WA", "Zipcode": "98102", "City": "Seattle", "Confidence_location": "high"},
        )

    def test_checkCapitalization(self):
        self.assertEqual(
            location_info.extract_location("washington 98102")["Zipcode"], "98102"
        )

    def test_checkCapitalization2(self):
        self.assertEqual(
            location_info.extract_location("WASHINGTON 98102")["Zipcode"], "98102"
        )

    def test_findsInFullSentence(self):
        self.assertEqual(
            location_info.extract_location(
                "something something happened in Washington 98102"
            )["Zipcode"],
            "98102",
        )

    def test_lowConfindenceIfNonMatchingZip(self):
        results_dict = location_info.extract_location("texas 10983")
        self.assertEqual(results_dict["Confidence_location"], "low")
        self.assertEqual(results_dict["State"], "TX")

    def test_checkingTwoWordedStates(self):
        self.assertEqual(
            location_info.extract_location("Washington DC 20022")["Zipcode"], "20022"
        )
        self.assertEqual(
            location_info.extract_location("Princeton New Jersey 08540")["Zipcode"], "08540"
        )


if __name__ == "__main__":
    unittest.main()
