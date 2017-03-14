# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.api.tests.utils import APITestCase
from freenasUI.network import models


class InterfaceResourceTest(APITestCase):

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
            'id': 1,
            'int_dhcp': False,
            'int_interface': 'em1',
            'int_ipv4address': '192.168.50.5',
            'int_ipv6address': '',
            'int_ipv6auto': False,
            'int_name': 'lan',
            'int_options': '',
            'int_v4netmaskbit': '24',
            'int_v6netmaskbit': '',
            'ipv4_addresses': ['192.168.50.5/24'],
            'ipv6_addresses': []
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
            'id': obj.id,
            'int_dhcp': False,
            'int_interface': 'em1',
            'int_ipv4address': '192.168.50.5',
            'int_ipv6address': '',
            'int_ipv6auto': False,
            'int_name': 'lan',
            'int_options': '',
            'int_v4netmaskbit': '24',
            'int_v6netmaskbit': '',
            'ipv4_addresses': ['192.168.50.5/24'],
            'ipv6_addresses': []
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
        self.assertHttpOK(resp)
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
            'id': 1,
            'sr_description': 'test route',
            'sr_destination': '192.168.1.111/24',
            'sr_gateway': '192.168.3.1'
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
            'id': obj.id,
            'sr_description': 'test route',
            'sr_destination': '192.168.1.111/24',
            'sr_gateway': '192.168.3.1'
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
        self.assertHttpOK(resp)
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
            'id': 1,
            'vlan_description': '',
            'vlan_pint': 'em1',
            'vlan_tag': 0,
            'vlan_vint': 'vlan0'
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
            'id': obj.id,
            'vlan_description': '',
            'vlan_pint': 'em1',
            'vlan_tag': 0,
            'vlan_vint': 'vlan0'
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
        self.assertHttpOK(resp)
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
        self.assertEqual(data, {
            'id': self._gc.id,
            'gc_domain': 'local',
            'gc_hostname': 'nas',
            'gc_hosts': '',
            'gc_ipv4gateway': '',
            'gc_ipv6gateway': '',
            'gc_nameserver1': '',
            'gc_nameserver2': '',
            'gc_nameserver3': '',
            'gc_httpproxy': '',
            'gc_netwait_enabled': False,
            'gc_netwait_ip': '',
        })

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._gc.id),
            format='json',
            data={
                'gc_hostname': 'mynas',
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._gc.id)
        self.assertEqual(data['gc_hostname'], 'mynas')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), self._gc.id),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class LAGGResourceTest(APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'lagg_interfaces': ['em1'],
                'lagg_protocol': 'roundrobin',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            'id': 1,
            'lagg_interface': 'lagg0',
            'lagg_protocol': 'roundrobin'
        })

    def test_Retrieve(self):
        iface = models.Interfaces.objects.create(
            int_interface='lagg0',
            int_name='lan',
            int_dhcp=False,
            int_ipv4address='192.168.50.5',
            int_v4netmaskbit='24',
        )
        obj = models.LAGGInterface.objects.create(
            lagg_interface=iface,
            lagg_protocol='roundrobin',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            'id': obj.id,
            'lagg_interface': 'lagg0',
            'lagg_protocol': 'roundrobin'
        }])

    def test_Update(self):
        iface = models.Interfaces.objects.create(
            int_interface='em1',
            int_name='lan',
            int_dhcp=False,
            int_ipv4address='192.168.50.5',
            int_v4netmaskbit='24',
        )
        obj = models.LAGGInterface.objects.create(
            lagg_interface=iface,
            lagg_protocol='roundrobin',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)

    def test_Delete(self):
        iface = models.Interfaces.objects.create(
            int_interface='em1',
            int_name='lan',
            int_dhcp=False,
            int_ipv4address='192.168.50.5',
            int_v4netmaskbit='24',
        )
        obj = models.LAGGInterface.objects.create(
            lagg_interface=iface,
            lagg_protocol='roundrobin',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)
