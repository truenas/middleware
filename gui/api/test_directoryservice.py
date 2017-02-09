# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.api.tests.utils import APITestCase
from freenasUI.network.models import GlobalConfiguration
from freenasUI.directoryservice import models
from freenasUI.storage.models import MountPoint, Volume


class ActiveDirectoryResourceTest(APITestCase):

    def setUp(self):
        super(ActiveDirectoryResourceTest, self).setUp()
        GlobalConfiguration.objects.create()
        self._obj = models.ActiveDirectory.objects.create()

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
            'id': self._obj.id,
            'ad_bindname': '',
            'ad_bindpw': '',
            'ad_allow_trusted_doms': False,
            'ad_dcname': '',
            'ad_dns_timeout': 10,
            'ad_domainname': '',
            'ad_gcname': '',
            'ad_idmap_backend': 'rid',
            'ad_netbiosname': 'NAS',
            'ad_timeout': 10,
            'ad_unix_extensions': False,
            'ad_use_default_domain': False,
            'ad_use_keytab': False,
            'ad_verbose_logging': False,
            'ad_certificate': '',
            'ad_enable': False,
            'ad_ssl': 'off',
        })

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'ad_netbiosname': 'mynas',
                'ad_domainname': 'mydomain',
                'ad_bindname': 'admin',
                'ad_bindpw': 'mypw',
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._obj.id)
        self.assertEqual(data['ad_netbiosname'], 'mynas')
        self.assertEqual(data['ad_domainname'], 'mydomain')
        self.assertEqual(data['ad_bindname'], 'admin')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class LDAPResourceTest(APITestCase):

    def setUp(self):
        super(LDAPResourceTest, self).setUp()
        self._obj = models.LDAP.objects.create()

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
            'id': self._obj.id,
            'ldap_anonbind': False,
            'ldap_basedn': '',
            'ldap_groupsuffix': '',
            'ldap_hostname': '',
            'ldap_machinesuffix': '',
            'ldap_passwordsuffix': '',
            'ldap_basedn': '',
            'ldap_bindpw': '',
            'ldap_binddn': '',
            'ldap_ssl': 'off',
            'ldap_idmap_backend': 'ldap',
            'ldap_usersuffix': '',
            'ldap_sudosuffix': '',
            'ldap_use_default_domain': False,
            'ldap_enable': False,
            'ldap_certfile': '',
        })

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'ldap_hostname': 'ldaphostname',
                'ldap_basedn': 'dc=test,dc=org',
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._obj.id)
        self.assertEqual(data['ldap_hostname'], 'ldaphostname')
        self.assertEqual(data['ldap_basedn'], 'dc=test,dc=org')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class NISResourceTest(APITestCase):

    def setUp(self):
        super(NISResourceTest, self).setUp()
        self._obj = models.NIS.objects.create()

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
            'id': self._obj.id,
            'nis_domain': '',
            'nis_manycast': False,
            'nis_secure_mode': False,
            'nis_servers': '',
            'nis_enable': False,
        })

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'nis_domain': 'nisdomain',
                'nis_secure_mode': True,
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._obj.id)
        self.assertEqual(data['nis_domain'], 'nisdomain')
        self.assertEqual(data['nis_secure_mode'], True)

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class NT4ResourceTest(APITestCase):

    def setUp(self):
        super(NT4ResourceTest, self).setUp()
        GlobalConfiguration.objects.create()
        self._obj = models.NT4.objects.create()

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
            'id': self._obj.id,
            'nt4_adminname': '',
            'nt4_adminpw': '',
            'nt4_dcname': '',
            'nt4_netbiosname': 'NAS',
            'nt4_workgroup': '',
            'nt4_idmap_backend': 'rid',
            'nt4_use_default_domain': False,
            'nt4_enable': False,
        })

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'nt4_dcname': 'mydcname',
                'nt4_netbiosname': 'netbios',
                'nt4_workgroup': 'WORKGROUP',
                'nt4_adminname': 'admin',
                'nt4_adminpw': 'mypw',
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._obj.id)
        self.assertEqual(data['nt4_dcname'], 'mydcname')
        self.assertEqual(data['nt4_netbiosname'], 'netbios')
        self.assertEqual(data['nt4_workgroup'], 'WORKGROUP')
        self.assertEqual(data['nt4_adminname'], 'admin')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)
