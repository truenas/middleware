from .utils import APITestCase
from freenasUI.network import models


"""
class InterfacesResourceTest(APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'int_interface': 'em1',
                'int_name': 'lan',
                'int_ipv4address': '192.168.50.5',
                'int_v4netmaskbit': '24',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'int_dhcp': False,
            u'int_interface': u'em1',
            u'int_ipv4address': u'192.168.50.5',
            u'int_ipv6address': u'',
            u'int_ipv6auto': False,
            u'int_name': u'lan',
            u'int_options': u'',
            u'int_v4netmaskbit': u'24',
            u'int_v6netmaskbit': u'',
            u'ipv4_addresses': [u'192.168.50.5/24'],
            u'ipv6_addresses': []
        })

    def test_Retrieve(self):
        obj = models.Interfaces.objects.create(
            int_interface='em1',
            int_name='lan',
            int_dhcp=False,
            int_ipv4address='192.168.50.5',
            int_v4netmaskbit='24',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'int_dhcp': False,
            u'int_interface': u'em1',
            u'int_ipv4address': u'192.168.50.5',
            u'int_ipv6address': u'',
            u'int_ipv6auto': False,
            u'int_name': u'lan',
            u'int_options': u'',
            u'int_v4netmaskbit': u'24',
            u'int_v6netmaskbit': u'',
            u'ipv4_addresses': [u'192.168.50.5/24'],
            u'ipv6_addresses': []
        }])

    def test_Update(self):
        obj = models.Interfaces.objects.create(
            int_interface='em1',
            int_name='lan',
            int_dhcp=False,
            int_ipv4address='192.168.50.5',
            int_v4netmaskbit='24',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'int_ipv4address': '192.168.50.6',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['int_ipv4address'], '192.168.50.6')

    def test_Delete(self):
        obj = models.Interfaces.objects.create(
            int_interface='em1',
            int_name='lan',
            int_dhcp=False,
            int_ipv4address='192.168.50.5',
            int_v4netmaskbit='24',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class StaticRouteResourceTest(APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'sr_destination': '192.168.1.111/24',
                'sr_gateway': '192.168.3.1',
                'sr_description': 'test route',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'sr_description': u'test route',
            u'sr_destination': u'192.168.1.111/24',
            u'sr_gateway': u'192.168.3.1'
        })

    def test_Retrieve(self):
        obj = models.StaticRoute.objects.create(
            sr_destination='192.168.1.111/24',
            sr_gateway='192.168.3.1',
            sr_description='test route',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'sr_description': u'test route',
            u'sr_destination': u'192.168.1.111/24',
            u'sr_gateway': u'192.168.3.1'
        }])

    def test_Update(self):
        obj = models.StaticRoute.objects.create(
            sr_destination='192.168.1.111/24',
            sr_gateway='192.168.3.1',
            sr_description='test route',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'sr_destination': '192.168.1.112/24',
                'sr_description': 'test route 2',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['sr_destination'], '192.168.1.112/24')
        self.assertEqual(data['sr_description'], 'test route 2')

    def test_Delete(self):
        obj = models.StaticRoute.objects.create(
            sr_destination='192.168.1.111/24',
            sr_gateway='192.168.3.1',
            sr_description='test route',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class VLANResourceTest(APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'vlan_vint': 'vlan0',
                'vlan_pint': 'em1',
                'vlan_tag': 0,
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'vlan_description': u'',
            u'vlan_pint': u'em1',
            u'vlan_tag': 0,
            u'vlan_vint': u'vlan0'
        })

    def test_Retrieve(self):
        obj = models.VLAN.objects.create(
            vlan_vint='vlan0',
            vlan_pint='em1',
            vlan_tag=0,
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'vlan_description': u'',
            u'vlan_pint': u'em1',
            u'vlan_tag': 0,
            u'vlan_vint': u'vlan0'
        }])

    def test_Update(self):
        obj = models.VLAN.objects.create(
            vlan_vint='vlan0',
            vlan_pint='em1',
            vlan_tag=0,
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'vlan_tag': 1,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['vlan_tag'], 1)

    def test_Delete(self):
        obj = models.VLAN.objects.create(
            vlan_vint='vlan0',
            vlan_pint='em1',
            vlan_tag=0,
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)
"""


class GlobalConfigurationResourceTest(APITestCase):

    def setUp(self):
        super(GlobalConfigurationResourceTest, self).setUp()
        self._gc = models.GlobalConfiguration.objects.create()

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
            u'id': self._gc.id,
            u'gc_domain': u'local',
            u'gc_hostname': u'nas',
            u'gc_hosts': u'',
            u'gc_ipv4gateway': u'',
            u'gc_ipv6gateway': u'',
            u'gc_nameserver1': u'',
            u'gc_nameserver2': u'',
            u'gc_nameserver3': u'',
            u'gc_netwait_enabled': False,
            u'gc_netwait_ip': u'',
        }])

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._gc.id),
            format='json',
            data={
                'gc_hostname': 'mynas',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._gc.id)
        self.assertEqual(data['gc_hostname'], 'mynas')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), self._gc.id),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)
