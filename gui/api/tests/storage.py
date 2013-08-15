from .utils import APITestCase
from freenasUI.api.models import APIClient


class VolumeResourceTest(APITestCase):

    def setUp(self):
        super(VolumeResourceTest, self).setUp()

    #def test_get_list_unauthorzied(self):
    #    self.assertHttpUnauthorized(
    #        self.api_client.get('/api/v1.0/storage/volume/', format='json')
    #    )

    def test_create_zpool(self):
        resp = self.api_client.post(
            '/api/v1.0/storage/volume/',
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

        resp = self.api_client.delete(
            '/api/v1.0/storage/volume/1/',
        )
        self.assertHttpAccepted(resp)
