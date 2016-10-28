from base import RESTTestCase


class AuthTestCase(RESTTestCase):

    def test_020_check_user(self):
        r = self.client.post('auth/check_user', data=[
            'root', 'freenas'
        ])
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertEqual(data, True)

        r = self.client.post('auth/check_user', data=[
            'root', 'freenas_fail'
        ])
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertEqual(data, False)

    def test_021_generate_token(self):
        r = self.client.post('auth/generate_token', data=[
            1000
        ])
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertIsInstance(data, unicode)
