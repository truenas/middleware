from .utils import APITestCase
from freenasUI.services import models
from freenasUI.storage.models import MountPoint, Volume


class ActiveDirectoryResourceTest(APITestCase):

    def setUp(self):
        super(ActiveDirectoryResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='directoryservice',
        )
        models.services.objects.create(
            srv_service='activedirectory',
        )
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
        self.assertEqual(data, [{
            u'id': self._obj.id,
            u'ad_adminname': u'',
            u'ad_adminpw': u'',
            u'ad_allow_trusted_doms': False,
            u'ad_dcname': u'',
            u'ad_dns_timeout': 10,
            u'ad_domainname': u'',
            u'ad_gcname': u'',
            u'ad_kpwdname': u'',
            u'ad_krbname': u'',
            u'ad_netbiosname': u'',
            u'ad_timeout': 10,
            u'ad_unix_extensions': False,
            u'ad_use_default_domain': True,
            u'ad_verbose_logging': False,
            u'ad_workgroup': u'',
        }])

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'ad_netbiosname': 'mynas',
                'ad_domainname': 'mydomain',
                'ad_workgroup': 'WORKGROUP',
                'ad_adminname': 'admin',
                'ad_adminpw': 'mypw',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._obj.id)
        self.assertEqual(data['ad_netbiosname'], 'mynas')
        self.assertEqual(data['ad_domainname'], 'mydomain')
        self.assertEqual(data['ad_workgroup'], 'WORKGROUP')
        self.assertEqual(data['ad_adminname'], 'admin')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


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
                'ddns_password2': 'mypass',  # FIXME: only 1 password
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


class LDAPResourceTest(APITestCase):

    def setUp(self):
        super(LDAPResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='directoryservice',
        )
        models.services.objects.create(
            srv_service='ldap',
        )
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
        self.assertEqual(data, [{
            u'id': self._obj.id,
            u'ldap_anonbind': False,
            u'ldap_basedn': u'',
            u'ldap_groupsuffix': u'',
            u'ldap_hostname': u'',
            u'ldap_machinesuffix': u'',
            u'ldap_options': u'',
            u'ldap_passwordsuffix': u'',
            u'ldap_pwencryption': u'clear',
            u'ldap_rootbasedn': u'',
            u'ldap_rootbindpw': u'',
            u'ldap_ssl': u'off',
            u'ldap_tls_cacertfile': u'',
            u'ldap_usersuffix': u''
        }])

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'ldap_hostname': 'ldaphostname',
                'ldap_basedn': 'dc=test,dc=org',
            }
        )
        self.assertHttpAccepted(resp)
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


class NISResourceTest(APITestCase):

    def setUp(self):
        super(NISResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='directoryservice',
        )
        models.services.objects.create(
            srv_service='nis',
        )
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
        self.assertEqual(data, [{
            u'id': self._obj.id,
            u'nis_domain': u'',
            u'nis_manycast': False,
            u'nis_secure_mode': False,
            u'nis_servers': u''
        }])

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'nis_domain': 'nisdomain',
                'nis_secure_mode': True,
            }
        )
        self.assertHttpAccepted(resp)
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
        models.services.objects.create(
            srv_service='directoryservice',
        )
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
        self.assertEqual(data, [{
            u'id': self._obj.id,
            u'nt4_adminname': u'',
            u'nt4_adminpw': u'',
            u'nt4_dcname': u'',
            u'nt4_netbiosname': u'',
            u'nt4_workgroup': u''
        }])

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
        self.assertHttpAccepted(resp)
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


class RsyncdResourceTest(APITestCase):

    def setUp(self):
        super(RsyncdResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='rsync',
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
        obj = models.Rsyncd.objects.create()
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'rsyncd_auxiliary': u'',
            u'rsyncd_port': 873
        }])

    def test_Update(self):
        obj = models.Rsyncd.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'rsyncd_port': 874,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['rsyncd_port'], 874)

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class RsyncModResourceTest(APITestCase):

    def setUp(self):
        super(RsyncModResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='rsync',
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
            data={
                'rsyncmod_name': 'testmod',
                'rsyncmod_path': '/mnt/tank',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'rsyncmod_auxiliary': u'',
            u'rsyncmod_comment': u'',
            u'rsyncmod_group': u'nobody',
            u'rsyncmod_hostsallow': u'',
            u'rsyncmod_hostsdeny': u'',
            u'rsyncmod_maxconn': 0,
            u'rsyncmod_mode': u'rw',
            u'rsyncmod_name': u'testmod',
            u'rsyncmod_path': u'/mnt/tank',
            u'rsyncmod_user': u'nobody'
        })

    def test_Retrieve(self):
        obj = models.RsyncMod.objects.create(
            rsyncmod_name='testmod',
            rsyncmod_path='/mnt/tank',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'rsyncmod_auxiliary': u'',
            u'rsyncmod_comment': u'',
            u'rsyncmod_group': u'nobody',
            u'rsyncmod_hostsallow': u'',
            u'rsyncmod_hostsdeny': u'',
            u'rsyncmod_maxconn': 0,
            u'rsyncmod_mode': u'rw',
            u'rsyncmod_name': u'testmod',
            u'rsyncmod_path': u'/mnt/tank',
            u'rsyncmod_user': u'nobody'
        }])

    def test_Update(self):
        obj = models.RsyncMod.objects.create(
            rsyncmod_name='testmod',
            rsyncmod_path='/mnt/tank',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'rsyncd_port': 874,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['rsyncd_port'], 874)

    def test_Delete(self):
        obj = models.RsyncMod.objects.create()
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class servicesResourceTest(APITestCase):

    def setUp(self):
        super(servicesResourceTest, self).setUp()
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
            data={
                'srv_service': 'test',
            }
        )
        self.assertHttpMethodNotAllowed(resp)

    def test_Retrieve(self):
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [
            {
                u'srv_service': u'ftp', u'srv_enable': False, u'id': 1,
            },
        ])

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
            data={
                'srv_enable': True,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['srv_enable'], True)

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class SMARTResourceTest(APITestCase):

    def setUp(self):
        super(SMARTResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='smartd',
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
        obj = models.SMART.objects.create()
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'smart_critical': 0,
            u'smart_difference': 0,
            u'smart_email': u'',
            u'smart_informational': 0,
            u'smart_interval': 30,
            u'smart_powermode': u'never'
        }])

    def test_Update(self):
        obj = models.SMART.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'smart_interval': 40,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['smart_interval'], 40)

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class SNMPResourceTest(APITestCase):

    def setUp(self):
        super(SNMPResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='snmp',
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
        obj = models.SNMP.objects.create()
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'snmp_community': u'public',
            u'snmp_contact': u'',
            u'snmp_location': u'',
            u'snmp_options': u'',
            u'snmp_traps': False
        }])

    def test_Update(self):
        obj = models.SNMP.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'snmp_contact': 'snmp@localhost.localdomain',
                'snmp_location': 'My Room',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['snmp_contact'], 'snmp@localhost.localdomain')
        self.assertEqual(data['snmp_location'], 'My Room')

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class SSHResourceTest(APITestCase):

    def setUp(self):
        super(SSHResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='ssh',
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
        obj = models.SSH.objects.create()
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'ssh_compression': False,
            u'ssh_host_dsa_key': u'',
            u'ssh_host_dsa_key_pub': u'',
            u'ssh_host_ecdsa_key': u'',
            u'ssh_host_ecdsa_key_pub': u'',
            u'ssh_host_key': u'',
            u'ssh_host_key_pub': u'',
            u'ssh_host_rsa_key': u'',
            u'ssh_host_rsa_key_pub': u'',
            u'ssh_options': u'',
            u'ssh_passwordauth': False,
            u'ssh_privatekey': u'',
            u'ssh_rootlogin': False,
            u'ssh_sftp_log_facility': u'',
            u'ssh_sftp_log_level': u'',
            u'ssh_tcpfwd': False,
            u'ssh_tcpport': 22
        }])

    def test_Update(self):
        obj = models.SSH.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'ssh_tcpfwd': True,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['ssh_tcpfwd'], True)

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


class iSCSITargetGlobalConfigurationResourceTest(APITestCase):

    resource_name = 'services/iscsi/globalconfiguration'

    def setUp(self):
        super(iSCSITargetGlobalConfigurationResourceTest, self).setUp()
        self._obj = models.iSCSITargetGlobalConfiguration.objects.create(
            iscsi_basename='iqn.2011-03.org.example.istgt',
        )
        models.services.objects.create(
            srv_service='iscsitarget',
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
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': self._obj.id,
            u'iscsi_basename': u'iqn.2011-03.org.example.istgt',
            u'iscsi_defaultt2r': 60,
            u'iscsi_defaultt2w': 2,
            u'iscsi_discoveryauthgroup': None,
            u'iscsi_discoveryauthmethod': u'Auto',
            u'iscsi_firstburst': 65536,
            u'iscsi_iotimeout': 30,
            u'iscsi_luc_authgroup': None,
            u'iscsi_luc_authmethod': u'CHAP',
            u'iscsi_luc_authnetwork': u'127.0.0.0/8',
            u'iscsi_lucip': u'127.0.0.1',
            u'iscsi_lucport': 3261,
            u'iscsi_maxburst': 262144,
            u'iscsi_maxconnect': 8,
            u'iscsi_maxoutstandingr2t': 16,
            u'iscsi_maxrecdata': 262144,
            u'iscsi_maxsesh': 16,
            u'iscsi_nopinint': 20,
            u'iscsi_r2t': 32,
            u'iscsi_toggleluc': False
        }])

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'iscsi_r2t': 64,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._obj.id)
        self.assertEqual(data['iscsi_r2t'], 64)

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class iSCSITargetExtentResourceTest(APITestCase):

    resource_name = 'services/iscsi/extent'

    def setUp(self):
        super(iSCSITargetExtentResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='iscsitarget',
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
            data={
                'iscsi_target_extent_name': 'extent',
                'iscsi_target_extent_type': 'File',
                'iscsi_target_extent_path': '/mnt/tank/iscsi',
                'iscsi_target_extent_filesize': '10MB',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'iscsi_target_extent_comment': u'',
            u'iscsi_target_extent_filesize': u'10MB',
            u'iscsi_target_extent_name': u'extent',
            u'iscsi_target_extent_path': u'/mnt/tank/iscsi',
            u'iscsi_target_extent_type': u'File'
        })

    def test_Retrieve(self):
        obj = models.iSCSITargetExtent.objects.create(
            iscsi_target_extent_name='extent',
            iscsi_target_extent_type='File',
            iscsi_target_extent_path='/mnt/tank/iscsi',
            iscsi_target_extent_filesize='10MB',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'iscsi_target_extent_comment': u'',
            u'iscsi_target_extent_filesize': u'10MB',
            u'iscsi_target_extent_name': u'extent',
            u'iscsi_target_extent_path': u'/mnt/tank/iscsi',
            u'iscsi_target_extent_type': u'File'
        }])

    def test_Update(self):
        obj = models.iSCSITargetExtent.objects.create(
            iscsi_target_extent_name='extent',
            iscsi_target_extent_type='File',
            iscsi_target_extent_path='/mnt/tank/iscsi',
            iscsi_target_extent_filesize='10MB',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'iscsi_target_extent_filesize': '20MB',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['iscsi_target_extent_filesize'], '20MB')

    def test_Delete(self):
        obj = models.iSCSITargetExtent.objects.create(
            iscsi_target_extent_name='extent',
            iscsi_target_extent_type='File',
            iscsi_target_extent_path='/mnt/tank/iscsi',
            iscsi_target_extent_filesize='10MB',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class iSCSITargetAuthorizedInitiatorResourceTest(APITestCase):

    resource_name = 'services/iscsi/authorizedinitiator'

    def setUp(self):
        super(iSCSITargetAuthorizedInitiatorResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='iscsitarget',
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
            data={
                'iscsi_target_initiator_initiators': 'ALL',
                'iscsi_target_initiator_auth_network': 'ALL',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'iscsi_target_initiator_auth_network': u'ALL',
            u'iscsi_target_initiator_comment': u'',
            u'iscsi_target_initiator_initiators': u'ALL',
            u'iscsi_target_initiator_tag': 1
        })

    def test_Retrieve(self):
        obj = models.iSCSITargetAuthorizedInitiator.objects.create(
            iscsi_target_initiator_initiators='ALL',
            iscsi_target_initiator_auth_network='ALL',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'iscsi_target_initiator_auth_network': u'ALL',
            u'iscsi_target_initiator_comment': u'',
            u'iscsi_target_initiator_initiators': u'ALL',
            u'iscsi_target_initiator_tag': 1
        }])

    def test_Update(self):
        obj = models.iSCSITargetAuthorizedInitiator.objects.create(
            iscsi_target_initiator_initiators='ALL',
            iscsi_target_initiator_auth_network='ALL',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'iscsi_target_initiator_auth_network': '192.168.0.0/16',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['iscsi_target_initiator_auth_network'],
                         '192.168.0.0/16')

    def test_Delete(self):
        obj = models.iSCSITargetAuthorizedInitiator.objects.create(
            iscsi_target_initiator_initiators='ALL',
            iscsi_target_initiator_auth_network='ALL',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class iSCSITargetAuthCredentialResourceTest(APITestCase):

    resource_name = 'services/iscsi/authcredential'

    def setUp(self):
        super(iSCSITargetAuthCredentialResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='iscsitarget',
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
                'iscsi_target_auth_tag': 1,
                'iscsi_target_auth_user': 'user',
                'iscsi_target_auth_secret': 'secret',
                'iscsi_target_auth_peeruser': 'peeruser',
                'iscsi_target_auth_peersecret': 'peersecret',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'iscsi_target_auth_peersecret': u'peersecret',
            u'iscsi_target_auth_peeruser': u'peeruser',
            u'iscsi_target_auth_secret': u'secret',
            u'iscsi_target_auth_tag': 1,
            u'iscsi_target_auth_user': u'user'
        })

    def test_Retrieve(self):
        obj = models.iSCSITargetAuthCredential.objects.create(
            iscsi_target_auth_user='user',
            iscsi_target_auth_secret='secret',
            iscsi_target_auth_peeruser='peeruser',
            iscsi_target_auth_peersecret='peersecret',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'iscsi_target_auth_peersecret': u'peersecret',
            u'iscsi_target_auth_peeruser': u'peeruser',
            u'iscsi_target_auth_secret': u'secret',
            u'iscsi_target_auth_tag': 1,
            u'iscsi_target_auth_user': u'user'
        }])

    def test_Update(self):
        obj = models.iSCSITargetAuthCredential.objects.create(
            iscsi_target_auth_user='user',
            iscsi_target_auth_secret='secret',
            iscsi_target_auth_peeruser='peeruser',
            iscsi_target_auth_peersecret='peersecret',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'iscsi_target_auth_user': 'user2',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['iscsi_target_auth_user'], 'user2')

    def test_Delete(self):
        obj = models.iSCSITargetAuthCredential.objects.create(
            iscsi_target_auth_user='user',
            iscsi_target_auth_secret='secret',
            iscsi_target_auth_peeruser='peeruser',
            iscsi_target_auth_peersecret='peersecret',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class iSCSITargetResourceTest(APITestCase):

    resource_name = 'services/iscsi/target'

    def setUp(self):
        super(iSCSITargetResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='iscsitarget',
        )
        self._portal = models.iSCSITargetPortal.objects.create()
        self._initiator = models.iSCSITargetAuthorizedInitiator.objects.create(
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
                'iscsi_target_name': 'target',
                'iscsi_target_portalgroup': self._portal.id,
                'iscsi_target_initiatorgroup': self._initiator.id,
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'iscsi_target_alias': None,
            u'iscsi_target_authgroup': None,
            u'iscsi_target_authtype': u'Auto',
            u'iscsi_target_flags': u'rw',
            u'iscsi_target_initialdigest': u'Auto',
            u'iscsi_target_initiatorgroup': 1,
            u'iscsi_target_logical_blocksize': 512,
            u'iscsi_target_name': u'target',
            u'iscsi_target_portalgroup': 1,
            u'iscsi_target_queue_depth': 32,
            u'iscsi_target_serial': u'10000001',
            u'iscsi_target_type': u'Disk'
        })

    def test_Retrieve(self):
        obj = models.iSCSITarget.objects.create(
            iscsi_target_name='target',
            iscsi_target_portalgroup=self._portal,
            iscsi_target_initiatorgroup=self._initiator,
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'iscsi_target_alias': None,
            u'iscsi_target_authgroup': None,
            u'iscsi_target_authtype': u'Auto',
            u'iscsi_target_flags': u'rw',
            u'iscsi_target_initialdigest': u'Auto',
            u'iscsi_target_logical_blocksize': 512,
            u'iscsi_target_name': u'target',
            u'iscsi_target_queue_depth': 32,
            u'iscsi_target_serial': u'10000001',
            u'iscsi_target_type': u'Disk'
        }])

    def test_Update(self):
        obj = models.iSCSITarget.objects.create(
            iscsi_target_name='target',
            iscsi_target_portalgroup=self._portal,
            iscsi_target_initiatorgroup=self._initiator,
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'iscsi_target_queue_depth': 64,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['iscsi_target_queue_depth'], 64)

    def test_Delete(self):
        obj = models.iSCSITarget.objects.create(
            iscsi_target_name='target',
            iscsi_target_portalgroup=self._portal,
            iscsi_target_initiatorgroup=self._initiator,
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class iSCSITargetToExtentResourceTest(APITestCase):

    resource_name = 'services/iscsi/targettoextent'

    def setUp(self):
        super(iSCSITargetToExtentResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='iscsitarget',
        )
        self._portal = models.iSCSITargetPortal.objects.create()
        self._initiator = models.iSCSITargetAuthorizedInitiator.objects.create(
        )
        self._target = models.iSCSITarget.objects.create(
            iscsi_target_name='target',
            iscsi_target_portalgroup=self._portal,
            iscsi_target_initiatorgroup=self._initiator,
        )
        self._extent = models.iSCSITargetExtent.objects.create(
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
                'iscsi_target': self._target.id,
                'iscsi_extent': self._extent.id,
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'iscsi_extent': 1,
            u'iscsi_target': 1,
        })

    def test_Retrieve(self):
        obj = models.iSCSITargetToExtent.objects.create(
            iscsi_target=self._target,
            iscsi_extent=self._extent,
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'iscsi_extent': 1,
            u'iscsi_target': 1,
        }])

    def test_Update(self):
        obj = models.iSCSITargetToExtent.objects.create(
            iscsi_target=self._target,
            iscsi_extent=self._extent,
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'iscsi_target_queue_depth': 64,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['iscsi_target_queue_depth'], 64)

    def test_Delete(self):
        obj = models.iSCSITargetToExtent.objects.create(
            iscsi_target=self._target,
            iscsi_extent=self._extent,
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class iSCSITargetPortalResourceTest(APITestCase):

    resource_name = 'services/iscsi/portal'

    def setUp(self):
        super(iSCSITargetPortalResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='iscsitarget',
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
                'iscsi_target_portal_comment': 'comment',
                'iscsi_target_portal_ips': ['0.0.0.0:3260'],
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'iscsi_target_portal_comment': u'comment',
            u'iscsi_target_portal_ips': [u'0.0.0.0:3260'],
            u'iscsi_target_portal_tag': 1
        })

    def test_Retrieve(self):
        obj = models.iSCSITargetPortal.objects.create()
        ip = models.iSCSITargetPortalIP.objects.create(
            iscsi_target_portalip_portal=obj,
            iscsi_target_portalip_ip='0.0.0.0',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'iscsi_target_portal_comment': u'',
            u'iscsi_target_portal_ips': [u'0.0.0.0:3260'],
            u'iscsi_target_portal_tag': 1
        }])

    def test_Update(self):
        obj = models.iSCSITargetPortal.objects.create()
        ip = models.iSCSITargetPortalIP.objects.create(
            iscsi_target_portalip_portal=obj,
            iscsi_target_portalip_ip='0.0.0.0',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'iscsi_target_portal_comment': 'comment2',
                'iscsi_target_portal_ips': ['0.0.0.0:3261'],
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['iscsi_target_portal_comment'], 'comment2')
        self.assertEqual(data['iscsi_target_portal_ips'], ['0.0.0.0:3261'])

    def test_Delete(self):
        obj = models.iSCSITargetPortal.objects.create()
        ip = models.iSCSITargetPortalIP.objects.create(
            iscsi_target_portalip_portal=obj,
            iscsi_target_portalip_ip='0.0.0.0',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class UPSResourceTest(APITestCase):

    def setUp(self):
        super(UPSResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='ups',
        )
        self._obj = models.UPS.objects.create()

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
            u'ups_description': u'',
            u'ups_driver': u'',
            u'ups_emailnotify': False,
            u'ups_extrausers': u'',
            u'ups_identifier': u'ups',
            u'ups_mode': u'master',
            u'ups_monpwd': u'fixmepass',
            u'ups_monuser': u'upsmon',
            u'ups_options': u'',
            u'ups_port': u'',
            u'ups_remotehost': u'',
            u'ups_remoteport': 3493,
            u'ups_rmonitor': False,
            u'ups_shutdown': u'batt',
            u'ups_shutdowntimer': 30,
            u'ups_subject': u'UPS report generated by %h',
            u'ups_toemail': u''
        }])

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'ups_rmonitor': True,
                'ups_port': '/mnt/tank/ups',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._obj.id)
        self.assertEqual(data['ups_rmonitor'], True)

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)
