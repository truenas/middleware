from .utils import APITestCase


class VolumeResourceTest(APITestCase):

    def setUp(self):
        super(VolumeResourceTest, self).setUp()
        self._create_zpool()

    def tearDown(self):
        super(VolumeResourceTest, self).tearDown()
        self._delete_zpool()

    def _create_zpool(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'volume_name': 'tankpool',
                'layout': [
                    {
                        'vdevtype': 'mirror',
                        'disks': ['ada4', 'ada5'],  # FIXME: use right disks
                    }
                ],
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data['children'], [])
        self.assertEqual(data['status'], "HEALTHY")
        self.assertEqual(data['vol_name'], "tankpool")
        self.assertEqual(data['vol_fstype'], "ZFS")
        self.assertEqual(data['vol_encrypt'], 0)
        self.assertEqual(data['mountpoint'], '/mnt/tankpool')

    def _delete_zpool(self):
        resp = self.api_client.delete(
            '%s1/' % self.get_api_url(),
        )
        self.assertHttpAccepted(resp)

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

