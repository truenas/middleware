from base import RESTTestCase


class CoreTestCase(RESTTestCase):

    def test_041_get_services(self):
        r = self.client.get('core/get_services')
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertIsInstance(data, dict)

    def test_042_get_methods(self):
        r = self.client.post('core/get_methods')
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertIsInstance(data, dict)

    def test_043_get_jobs(self):
        r = self.client.post('core/get_jobs')
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertIsInstance(data, list)

    def test_044_ping(self):
        r = self.client.get('core/ping')
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertEqual(data, 'pong')
