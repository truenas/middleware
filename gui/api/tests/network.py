from .utils import APITestCase
from freenasUI.network import models


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
