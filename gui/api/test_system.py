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
            'id': 1,
            'ntp_address': '0.freebsd.pool.ntp.org',
            'ntp_burst': False,
            'ntp_iburst': True,
            'ntp_maxpoll': 10,
            'ntp_minpoll': 6,
            'ntp_prefer': False
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
            'id': obj.id,
            'ntp_address': '0.freebsd.pool.ntp.org',
            'ntp_burst': False,
            'ntp_iburst': True,
            'ntp_maxpoll': 10,
            'ntp_minpoll': 6,
            'ntp_prefer': False
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
            'id': 1,
            'tun_comment': '',
            'tun_enabled': True,
            'tun_value': 'YES',
            'tun_var': 'xhci_load',
            'tun_type': 'loader',
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
            'id': obj.id,
            'tun_comment': '',
            'tun_enabled': True,
            'tun_value': 'YES',
            'tun_var': 'xhci_load',
            'tun_type': 'loader',
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
            'id': self._settings.id,
            'stg_guiaddress': '0.0.0.0',
            'stg_guihttpsport': 443,
            'stg_guiport': 80,
            'stg_guihttpsredirect': True,
            'stg_guiprotocol': 'http',
            'stg_guiv6address': '::',
            'stg_kbdmap': '',
            'stg_language': 'en',
            'stg_syslogserver': '',
            'stg_timezone': 'America/Los_Angeles',
            'stg_wizardshown': False
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
            'id': self._advanced.id,
            'adv_advancedmode': False,
            'adv_anonstats': True,
            'adv_anonstats_token': '',
            'adv_autotune': False,
            'adv_consolemenu': False,
            'adv_consolemsg': True,
            'adv_consolescreensaver': False,
            'adv_debugkernel': False,
            'adv_motd': 'Welcome',
            'adv_powerdaemon': False,
            'adv_serialconsole': False,
            'adv_serialport': '0x2f8',
            'adv_serialspeed': '9600',
            'adv_swapondrive': 2,
            'adv_traceback': True,
            'adv_uploadcrash': True,
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
            'id': self._obj.id,
            'em_fromemail': '',
            'em_outgoingserver': '',
            'em_pass': None,
            'em_port': 25,
            'em_security': 'plain',
            'em_smtp': False,
            'em_user': None,
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
            'id': self._obj.id,
            'ssl_certfile': '',
            'ssl_city': None,
            'ssl_common': None,
            'ssl_country': None,
            'ssl_email': None,
            'ssl_org': None,
            'ssl_passphrase': None,
            'ssl_state': None,
            'ssl_unit': None
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
