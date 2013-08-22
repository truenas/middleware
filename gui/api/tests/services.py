from .utils import APITestCase
from freenasUI.services import models
from freenasUI.storage.models import MountPoint, Volume


class AFPResourceTest(APITestCase):

    def setUp(self):
        super(AFPResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='afp',
        )
        v = Volume.objects.create(
            vol_name='tank',
            vol_fstype='ZFS',
        )
        MountPoint.objects.create(
            mp_path='/mnt/tank',
            mp_volume=v,
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
        obj = models.AFP.objects.create()
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'afp_srv_connections_limit': 50,
            u'afp_srv_guest': False,
            u'afp_srv_guest_user': u'nobody',
            u'afp_srv_name': u''
        }])

    def test_Update(self):
        obj = models.AFP.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'afp_srv_name': 'freenas',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['afp_srv_name'], 'freenas')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class CIFSResourceTest(APITestCase):

    def setUp(self):
        super(CIFSResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='cifs',
        )
        v = Volume.objects.create(
            vol_name='tank',
            vol_fstype='ZFS',
        )
        MountPoint.objects.create(
            mp_path='/mnt/tank',
            mp_volume=v,
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
        obj = models.CIFS.objects.create()
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'cifs_srv_aio_enable': False,
            u'cifs_srv_aio_rs': 4096,
            u'cifs_srv_aio_ws': 4096,
            u'cifs_srv_authmodel': u'user',
            u'cifs_srv_description': u'',
            u'cifs_srv_dirmask': u'',
            u'cifs_srv_dosattr': False,
            u'cifs_srv_doscharset': u'CP437',
            u'cifs_srv_easupport': False,
            u'cifs_srv_filemask': u'',
            u'cifs_srv_guest': u'nobody',
            u'cifs_srv_homedir': None,
            u'cifs_srv_homedir_aux': u'',
            u'cifs_srv_homedir_browseable_enable': False,
            u'cifs_srv_homedir_enable': False,
            u'cifs_srv_hostlookup': True,
            u'cifs_srv_localmaster': False,
            u'cifs_srv_loglevel': u'1',
            u'cifs_srv_netbiosname': u'',
            u'cifs_srv_nullpw': False,
            u'cifs_srv_smb_options': u'',
            u'cifs_srv_timeserver': False,
            u'cifs_srv_unixcharset': u'UTF-8',
            u'cifs_srv_unixext': True,
            u'cifs_srv_workgroup': u'',
            u'cifs_srv_zeroconf': True
        }])

    def test_Update(self):
        obj = models.CIFS.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'cifs_srv_netbiosname': 'MYTEST',
                'cifs_srv_workgroup': 'MYGROUP',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['cifs_srv_netbiosname'], 'MYTEST')
        self.assertEqual(data['cifs_srv_workgroup'], 'MYGROUP')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class DynamicDNSResourceTest(APITestCase):

    def setUp(self):
        super(DynamicDNSResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='dynamicdns',
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
        obj = models.DynamicDNS.objects.create()
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'ddns_domain': u'',
            u'ddns_fupdateperiod': u'',
            u'ddns_options': u'',
            u'ddns_password': u'',
            u'ddns_provider': u'dyndns@dyndns.org',
            u'ddns_updateperiod': u'',
            u'ddns_username': u'',
        }])

    def test_Update(self):
        obj = models.DynamicDNS.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'ddns_username': 'testuser',
                'ddns_password': 'mypass',
                'ddns_password2': 'mypass',  #FIXME: only 1 password
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['ddns_username'], 'testuser')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class FTPResourceTest(APITestCase):

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
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class NFSResourceTest(APITestCase):

    def setUp(self):
        super(NFSResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='nfs',
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
        obj = models.NFS.objects.create()
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'nfs_srv_allow_nonroot': False,
            u'nfs_srv_bindip': u'',
            u'nfs_srv_mountd_port': None,
            u'nfs_srv_rpclockd_port': None,
            u'nfs_srv_rpcstatd_port': None,
            u'nfs_srv_servers': 4
        }])

    def test_Update(self):
        obj = models.NFS.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'nfs_srv_servers': 10,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['nfs_srv_servers'], 10)

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class TFTPResourceTest(APITestCase):

    def setUp(self):
        super(TFTPResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='tftp',
        )
        v = Volume.objects.create(
            vol_name='tank',
            vol_fstype='ZFS',
        )
        MountPoint.objects.create(
            mp_path='/mnt/tank',
            mp_volume=v,
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
        obj = models.TFTP.objects.create()
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'tftp_directory': u'',
            u'tftp_newfiles': False,
            u'tftp_options': u'',
            u'tftp_port': 69,
            u'tftp_umask': u'022',
            u'tftp_username': u'nobody'
        }])

    def test_Update(self):
        obj = models.TFTP.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'tftp_directory': '/mnt/tank',
                'tftp_newfiles': True,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['tftp_newfiles'], True)

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)
