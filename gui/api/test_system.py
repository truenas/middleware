# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.api.tests.utils import APITestCase
from freenasUI.storage.models import Disk, MountPoint, Volume
from freenasUI.system import models


class NTPServerResourceTest(APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'ntp_address': '0.freebsd.pool.ntp.org',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'ntp_address': u'0.freebsd.pool.ntp.org',
            u'ntp_burst': False,
            u'ntp_iburst': True,
            u'ntp_maxpoll': 10,
            u'ntp_minpoll': 6,
            u'ntp_prefer': False
        })

    def test_Retrieve(self):
        obj = models.NTPServer.objects.create(
            ntp_address='0.freebsd.pool.ntp.org',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'ntp_address': u'0.freebsd.pool.ntp.org',
            u'ntp_burst': False,
            u'ntp_iburst': True,
            u'ntp_maxpoll': 10,
            u'ntp_minpoll': 6,
            u'ntp_prefer': False
        }])

    def test_Update(self):
        obj = models.NTPServer.objects.create(
            ntp_address='0.freebsd.pool.ntp.org',
            ntp_prefer=False,
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'ntp_prefer': True,
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['ntp_prefer'], True)

    def test_Delete(self):
        obj = models.NTPServer.objects.create(
            ntp_address='0.freebsd.pool.ntp.org',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class TunableResourceTest(APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'tun_var': 'xhci_load',
                'tun_value': 'YES',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'tun_comment': u'',
            u'tun_enabled': True,
            u'tun_value': u'YES',
            u'tun_var': u'xhci_load',
            u'tun_type': u'loader',
        })

    def test_Retrieve(self):
        obj = models.Tunable.objects.create(
            tun_var='xhci_load',
            tun_value='YES',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'tun_comment': u'',
            u'tun_enabled': True,
            u'tun_value': u'YES',
            u'tun_var': u'xhci_load',
            u'tun_type': u'loader',
        }])

    def test_Update(self):
        obj = models.Tunable.objects.create(
            tun_var='xhci_load',
            tun_value='YES',
            tun_type='loader',
            tun_enabled=True
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'tun_enabled': False,
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['tun_enabled'], False)

    def test_Delete(self):
        obj = models.Tunable.objects.create(
            tun_var='xhci_load',
            tun_value='YES',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class SettingsResourceTest(APITestCase):

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
            u'id': self._settings.id,
            u'stg_guiaddress': u'0.0.0.0',
            u'stg_guihttpsport': 443,
            u'stg_guiport': 80,
            u'stg_guihttpsredirect': True,
            u'stg_guiprotocol': u'http',
            u'stg_guiv6address': u'::',
            u'stg_kbdmap': u'',
            u'stg_language': u'en',
            u'stg_syslogserver': u'',
            u'stg_timezone': u'America/Los_Angeles',
            u'stg_wizardshown': False
        })

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._settings.id),
            format='json',
            data={
                'stg_timezone': 'America/Sao_Paulo',
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._settings.id)
        self.assertEqual(data['stg_timezone'], 'America/Sao_Paulo')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class AdvancedResourceTest(APITestCase):

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
            u'id': self._advanced.id,
            u'adv_advancedmode': False,
            u'adv_anonstats': True,
            u'adv_anonstats_token': u'',
            u'adv_autotune': False,
            u'adv_consolemenu': False,
            u'adv_consolemsg': True,
            u'adv_consolescreensaver': False,
            u'adv_debugkernel': False,
            u'adv_motd': u'Welcome',
            u'adv_powerdaemon': False,
            u'adv_serialconsole': False,
            u'adv_serialport': u'0x2f8',
            u'adv_serialspeed': u'9600',
            u'adv_swapondrive': 2,
            u'adv_traceback': True,
            u'adv_uploadcrash': True,
        })

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._advanced.id),
            format='json',
            data={
                'adv_powerdaemon': True,
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._advanced.id)
        self.assertEqual(data['adv_powerdaemon'], True)

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class EmailResourceTest(APITestCase):

    def setUp(self):
        super(EmailResourceTest, self).setUp()
        self._obj = models.Email.objects.create()

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
            u'em_fromemail': u'',
            u'em_outgoingserver': u'',
            u'em_pass': None,
            u'em_port': 25,
            u'em_security': u'plain',
            u'em_smtp': False,
            u'em_user': None,
        })

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'em_fromemail': 'dev@ixsystems.com',
                'em_outgoingserver': 'mail.ixsystems.com',
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._obj.id)
        self.assertEqual(data['em_fromemail'], 'dev@ixsystems.com')
        self.assertEqual(data['em_outgoingserver'], 'mail.ixsystems.com')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class SSLResourceTest(APITestCase):

    def setUp(self):
        super(SSLResourceTest, self).setUp()
        self._obj = models.SSL.objects.create()

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
            u'ssl_certfile': u'',
            u'ssl_city': None,
            u'ssl_common': None,
            u'ssl_country': None,
            u'ssl_email': None,
            u'ssl_org': None,
            u'ssl_passphrase': None,
            u'ssl_state': None,
            u'ssl_unit': None
        })

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                "ssl_city": 'Curitiba',
                "ssl_common": 'iXsystems',
                "ssl_country": 'BR',
                "ssl_email": 'william@ixsystems.com',
                "ssl_org": 'iXsystems',
                "ssl_state": 'Parana',
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._obj.id)
        self.assertEqual(data['ssl_city'], 'Curitiba')
        self.assertEqual(data['ssl_common'], 'iXsystems')
        self.assertEqual(data['ssl_country'], 'BR')
        self.assertEqual(data['ssl_email'], 'william@ixsystems.com')
        self.assertEqual(data['ssl_org'], 'iXsystems')
        self.assertEqual(data['ssl_state'], 'Parana')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)
