import sys
import os

path =  os.path.join('workflow', 'extract')
sys.path.append(path)

import location_info_Google 
import unittest

class MyTest(unittest.TestCase):
    def test_isNotNone(self):
    	self.assertIsNotNone(location_info_Google.extract_location("Washington 98102"))
    def test_basic(self):
        self.assertEqual(location_info_Google.extract_location("Washington 98102"), {'State': 'WA',
            'Zipcode': '98102', 'City':'Seattle', 'Confidence_location': 'high'})
    def test_checkCapitalization(self):
        self.assertEqual(location_info_Google.extract_location("washington 98102")['Zipcode'], '98102')
    def test_failIfNonMatchingZip(self):
    	self.assertEqual(location_info_Google.extract_location('texas 10983')['Confidence_location'], 'low')

if __name__ == '__main__':
    unittest.main()