# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.api.tests.utils import APITestCase
from freenasUI.jails import models
from freenasUI.common.warden import WARDEN_TYPE_PLUGINJAIL


class JailsResourceTest(APITestCase):

    def setUp(self):
        super(JailsResourceTest, self).setUp()
        self._jc = models.JailsConfiguration.objects.create(
            jc_path='/mnt/tank/jails',
        )

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'jail_host': 'myjail',
                'jail_type': WARDEN_TYPE_PLUGINJAIL,
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)
        #obj = models.Jails.objects.filter(jail_host='myjail')[0]

        data = self.deserialize(resp)
        self.assertEqual(data, {
            'id': 1,
            'jail_alias_bridge_ipv4': None,
            'jail_alias_bridge_ipv6': None,
            'jail_alias_ipv4': None,
            'jail_alias_ipv6': None,
            'jail_autostart': False,
            'jail_bridge_ipv4': '',
            'jail_bridge_ipv6': '',
            'jail_defaultrouter_ipv4': '',
            'jail_defaultrouter_ipv6': '',
            'jail_host': 'myjail',
            'jail_ipv4': '',
            'jail_ipv6': '',
            'jail_mac': '',
            'jail_nat': False,
            'jail_status': '',
            'jail_type': 'pluginjail',
            'jail_vnet': False
        })

    def test_Retrieve(self):
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            'id': 1,
            'jail_alias_bridge_ipv4': None,
            'jail_alias_bridge_ipv6': None,
            'jail_alias_ipv4': None,
            'jail_alias_ipv6': None,
            'jail_autostart': False,
            'jail_bridge_ipv4': '',
            'jail_bridge_ipv6': '',
            'jail_defaultrouter_ipv4': '',
            'jail_defaultrouter_ipv6': '',
            'jail_host': 'myjail',
            'jail_ipv4': '',
            'jail_ipv6': '',
            'jail_mac': '',
            'jail_nat': False,
            'jail_status': '',
            'jail_type': 'pluginjail',
            'jail_vnet': False
        }])

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
            data={
                'jail_autostart': False,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        #self.assertEqual(data['id'], obj.id)

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpAccepted(resp)


class JailsConfigurationResourceTest(APITestCase):

    def setUp(self):
        super(JailsConfigurationResourceTest, self).setUp()
        self._obj = models.JailsConfiguration.objects.create()

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)

    def test_Retrieve(self):
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            'id': self._obj.id,
            'jc_ipv4_network': '192.168.3.0/24',
            'jc_ipv4_network_end': '192.168.3.254',
            'jc_ipv4_network_start': '192.168.3.67',
            'jc_ipv6_network': '',
            'jc_ipv6_network_end': '',
            'jc_ipv6_network_start': '',
            'jc_path': ''
        }])

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'jc_path': '/mnt/tank/jails',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._obj.id)
        self.assertEqual(data['jc_path'], '/mnt/tank/jails')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)
