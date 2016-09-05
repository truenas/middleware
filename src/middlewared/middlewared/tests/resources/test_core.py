from base import RESTTestCase


class VolumeCreateTestCase(RESTTestCase):

    def test_041_get_services(self):
        r = self.client.get('core/get_services')
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertIsInstance(data, dict)

    def test_042_get_methods(self):
        r = self.client.get('core/get_methods')
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertIsInstance(data, dict)
