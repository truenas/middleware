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
            u'id': self._obj.id,
            u'ad_bindname': u'',
            u'ad_bindpw': u'',
            u'ad_allow_trusted_doms': False,
            u'ad_dcname': u'',
            u'ad_dns_timeout': 10,
            u'ad_domainname': u'',
            u'ad_gcname': u'',
            u'ad_keytab': u'',
            u'ad_kpwdname': u'',
            u'ad_krbname': u'',
            u'ad_netbiosname': u'NAS',
            u'ad_timeout': 10,
            u'ad_unix_extensions': False,
            u'ad_use_default_domain': True,
            u'ad_use_keytab': False,
            u'ad_verbose_logging': False,
            u'ad_certfile': u'',
            u'ad_enable': False,
            u'ad_ssl': u'off',
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
            u'id': self._obj.id,
            u'ldap_anonbind': False,
            u'ldap_basedn': u'',
            u'ldap_groupsuffix': u'',
            u'ldap_hostname': u'',
            u'ldap_machinesuffix': u'',
            u'ldap_passwordsuffix': u'',
            u'ldap_basedn': u'',
            u'ldap_bindpw': u'',
            u'ldap_binddn': u'',
            u'ldap_ssl': u'off',
            u'ldap_idmap_backend': u'ldap',
            u'ldap_usersuffix': u'',
            u'ldap_sudosuffix': u'',
            u'ldap_use_default_domain': False,
            u'ldap_enable': False,
            u'ldap_certfile': u'',
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
            u'id': self._obj.id,
            u'nis_domain': u'',
            u'nis_manycast': False,
            u'nis_secure_mode': False,
            u'nis_servers': u'',
            u'nis_enable': False,
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
            u'id': self._obj.id,
            u'nt4_adminname': u'',
            u'nt4_adminpw': u'',
            u'nt4_dcname': u'',
            u'nt4_netbiosname': u'NAS',
            u'nt4_workgroup': u'',
            u'nt4_idmap_backend': u'rid',
            u'nt4_use_default_domain': False,
            u'nt4_enable': False,
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
