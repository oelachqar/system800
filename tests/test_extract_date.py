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
    def test_noMins(self):
        self.assertEqual(date_info.extract_date_time('april thirteenth two thousand and sixteen at two PM')['minute'],0)
    def test_curveBallStreet(self):
        self.assertDictEqual(date_info.extract_date_time('blah blah thirty one may st new york new york on april third,\
            two thousand seventeen at one thirty PM blah blah'), 
            {'year': 2017, 'month': 4, 'day': 3, 'hour': 13, 'minute': 30})
    def test_digits(self):
        self.assertDictEqual(date_info.extract_date_time('new york on april 3rd, 2017 at 1:30 PM '), 
            {'year': 2017, 'month': 4, 'day': 3, 'hour': 13, 'minute': 30})
    def test_curveBallJudgeAndStreet(self):
        self.assertDictEqual(date_info.extract_date_time('judge may smith at address involving march and twenty third st '
         'on march third two thousand twenty one at one forty five AM'), 
         {'year': 2021, 'month': 3, 'day': 3, 'hour': 1, 'minute': 45})


if __name__ == "__main__":
    unittest.main()
