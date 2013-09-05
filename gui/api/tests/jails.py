from .utils import APITestCase
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
            u'id': 1,
            u'jail_alias_bridge_ipv4': None,
            u'jail_alias_bridge_ipv6': None,
            u'jail_alias_ipv4': None,
            u'jail_alias_ipv6': None,
            u'jail_autostart': False,
            u'jail_bridge_ipv4': u'',
            u'jail_bridge_ipv6': u'',
            u'jail_defaultrouter_ipv4': u'',
            u'jail_defaultrouter_ipv6': u'',
            u'jail_host': u'myjail',
            u'jail_ipv4': u'',
            u'jail_ipv6': u'',
            u'jail_mac': u'',
            u'jail_nat': False,
            u'jail_status': u'',
            u'jail_type': u'pluginjail',
            u'jail_vnet': False
        })

    def test_Retrieve(self):
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': 1,
            u'jail_alias_bridge_ipv4': None,
            u'jail_alias_bridge_ipv6': None,
            u'jail_alias_ipv4': None,
            u'jail_alias_ipv6': None,
            u'jail_autostart': False,
            u'jail_bridge_ipv4': u'',
            u'jail_bridge_ipv6': u'',
            u'jail_defaultrouter_ipv4': u'',
            u'jail_defaultrouter_ipv6': u'',
            u'jail_host': u'myjail',
            u'jail_ipv4': u'',
            u'jail_ipv6': u'',
            u'jail_mac': u'',
            u'jail_nat': False,
            u'jail_status': u'',
            u'jail_type': u'pluginjail',
            u'jail_vnet': False
        }])

    maxDiff = None
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
        self.assertEqual(data['id'], obj.id)

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
            u'id': self._obj.id,
            u'jc_ipv4_network': u'192.168.3.0/24',
            u'jc_ipv4_network_end': u'192.168.3.254',
            u'jc_ipv4_network_start': u'192.168.3.67',
            u'jc_ipv6_network': u'',
            u'jc_ipv6_network_end': u'',
            u'jc_ipv6_network_start': u'',
            u'jc_path': u''
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
