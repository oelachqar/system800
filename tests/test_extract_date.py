import unittest

from workflow.extract import date_info

class MyTest(unittest.TestCase):
    def test_basic(self):
        self.assertDictEqual(date_info.extract_date_time('april thirteen two thousand nineteen at four thirty PM'),
            {'year': 2019, 'month': 4, 'day': 13, 'hour': 16, 'minute': 30})
    def test_AMPM(self):
        self.assertNotEqual(date_info.extract_date_time('april thirteen two thousand nineteen at four thirty AM'),
            date_info.extract_date_time('april thirteen two thousand nineteen at four thirty PM'))
    def test_homonyms(self):
        self.assertEqual(date_info.extract_date_time('april thirteen two thousand nineteen at for thirty AM')['hour'], 4)
    def test_and(self):
        self.assertDictEqual(date_info.extract_date_time('april thirteenth two thousand and sixteen at two thirty PM'),
            date_info.extract_date_time('april thirteenth two thousand sixteen at two thirty PM'))
    def test_nomins(self):
        self.assertEqual(date_info.extract_date_time('april thirteenth two thousand and sixteen at two PM')['minute'],0)
  

if __name__ == "__main__":
    unittest.main()
