import config
from api.db import mongodb_client as db
import unittest
from run import create_app


class TestDataObjects(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        "set up test fixtures"
        print('### Setting up flask server ###')
        app = create_app()
        self.app = app.test_client()
        
        
    def test_persons(self):
        """ Test that the flask server is running and reachable"""

        r = self.app.get('http://127.0.0.1:8000/v1.0/time_travellers/persons')
        self.assertEqual(r.status_code, 200)
