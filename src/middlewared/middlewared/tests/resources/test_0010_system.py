from base import RESTTestCase


class SystemTestCase(RESTTestCase):

    def test_040_version(self):
        r = self.client.get('system/version')
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertIsInstance(data, str)

    def test_041_info(self):
        r = self.client.get('system/info')
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertIsInstance(data, dict)
