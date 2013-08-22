from .utils import APITestCase
from freenasUI.services import models


class FTPResourceTest(APITestCase):

    maxDiff = None

    def setUp(self):
        super(FTPResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='ftp',
        )

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
        obj = models.FTP.objects.create()
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'ftp_anonpath': None,
            u'ftp_anonuserbw': 0,
            u'ftp_anonuserdlbw': 0,
            u'ftp_banner': u'',
            u'ftp_clients': 32,
            u'ftp_defaultroot': False,
            u'ftp_dirmask': u'077',
            u'ftp_filemask': u'077',
            u'ftp_fxp': False,
            u'ftp_ident': False,
            u'ftp_ipconnections': 0,
            u'ftp_localuserbw': 0,
            u'ftp_localuserdlbw': 0,
            u'ftp_loginattempt': 3,
            u'ftp_masqaddress': u'',
            u'ftp_onlyanonymous': False,
            u'ftp_onlylocal': False,
            u'ftp_options': u'',
            u'ftp_passiveportsmax': 0,
            u'ftp_passiveportsmin': 0,
            u'ftp_port': 21,
            u'ftp_resume': False,
            u'ftp_reversedns': False,
            u'ftp_rootlogin': False,
            u'ftp_ssltls_certfile': u'',
            u'ftp_timeout': 120,
            u'ftp_tls': False,
        }])

    def test_Update(self):
        obj = models.FTP.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'ftp_filemask': '066',
                'ftp_dirmask': '067',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['ftp_filemask'], '066')
        self.assertEqual(data['ftp_dirmask'], '067')

    def test_Delete(self):
        obj = models.FTP.objects.create()
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)
