import unittest
from unittest import mock

from api.app import celery
from api.tasks import SendResult


class TestCeleryTasks(unittest.TestCase):
    def setUp(self):
        celery.conf.update(CELERY_ALWAYS_EAGER=True)

    @mock.patch("api.tasks.requests.post")
    def test_send_result(self, requests_post):
        data = {"date": "random_data", "location": "random_location"}
        callback_url = "callback_url"

        task = SendResult()

        # execute task
        task(data=data, callback_url=callback_url, ain="", outer_task_id="")

        # make sure data was posted to callback_url
        requests_post.assert_called_with(callback_url, json=data)


if __name__ == "__main__":
    unittest.main()
