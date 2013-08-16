from .utils import APITestCase
from freenasUI.system import models


class SysctlResourceTest(APITestCase):

    def setUp(self):
        super(SysctlResourceTest, self).setUp()

    def tearDown(self):
        super(SysctlResourceTest, self).tearDown()

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get('/api/v1.0/system/sysctl/', format='json')
        )

    def test_Create_sysctl(self):
        resp = self.api_client.post(
            '/api/v1.0/system/sysctl/',
            format='json',
            data={
                'sysctl_mib': 'kern.coredump',
                'sysctl_enabled': True,
                'sysctl_value': '1',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'sysctl_comment': u'',
            u'sysctl_enabled': True,
            u'sysctl_mib': u'kern.coredump',
            u'sysctl_value': u'1',
        })

    def test_Retrieve_sysctl(self):
        sysctl = models.Sysctl.objects.create(
            sysctl_mib='kern.coredump',
            sysctl_value='2',
        )
        resp = self.api_client.get(
            '/api/v1.0/system/sysctl/',
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [
            {
                u'id': sysctl.id,
                u'sysctl_comment': sysctl.sysctl_comment,
                u'sysctl_enabled': sysctl.sysctl_enabled,
                u'sysctl_mib': sysctl.sysctl_mib,
                u'sysctl_value': sysctl.sysctl_value,
            }
        ])

    def test_Update_sysctl(self):
        sysctl = models.Sysctl.objects.create(
            sysctl_mib='kern.coredump',
            sysctl_value='1',
        )
        resp = self.api_client.put(
            '/api/v1.0/system/sysctl/%d/' % sysctl.id,
            format='json',
            data={
                'sysctl_mib': 'kern.coredump',
                'sysctl_value': '2',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], sysctl.id)
        self.assertEqual(data['sysctl_value'], '2')

    def test_Delete_sysctl(self):
        sysctl = models.Sysctl.objects.create(
            sysctl_mib='kern.coredump',
            sysctl_value='1',
        )
        resp = self.api_client.delete(
            '/api/v1.0/system/sysctl/%d/' % sysctl.id,
            format='json',
        )
        self.assertHttpAccepted(resp)
