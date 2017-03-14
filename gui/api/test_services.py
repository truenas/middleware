# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.api.tests.utils import APITestCase
from freenasUI.network.models import GlobalConfiguration
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
        self.assertEqual(data, {
            'id': obj.id,
            'afp_srv_connections_limit': 50,
            'afp_srv_guest': False,
            'afp_srv_guest_user': 'nobody',
            'afp_srv_homedir': None,
            'afp_srv_homedir_enable': False,
            'afp_srv_dbpath': None,
            'afp_srv_global_aux': '',
        })

    def test_Update(self):
        obj = models.AFP.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'afp_srv_guest': True,
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['afp_srv_guest'], True)

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
        self.assertEqual(data, {
            'id': obj.id,
            'cifs_SID': None,
            'cifs_srv_aio_enable': False,
            'cifs_srv_aio_rs': 4096,
            'cifs_srv_aio_ws': 4096,
            'cifs_srv_allow_execute_always': True,
            'cifs_srv_description': '',
            'cifs_srv_dirmask': '',
            'cifs_srv_domain_logons': False,
            'cifs_srv_doscharset': 'CP437',
            'cifs_srv_filemask': '',
            'cifs_srv_guest': 'nobody',
            'cifs_srv_homedir': None,
            'cifs_srv_homedir_aux': '',
            'cifs_srv_homedir_browseable_enable': False,
            'cifs_srv_homedir_enable': False,
            'cifs_srv_hostlookup': True,
            'cifs_srv_localmaster': False,
            'cifs_srv_loglevel': '0',
            'cifs_srv_max_protocol': 'SMB2',
            'cifs_srv_min_protocol': '',
            'cifs_srv_syslog': False,
            'cifs_srv_netbiosname': '',
            'cifs_srv_nullpw': False,
            'cifs_srv_obey_pam_restrictions': True,
            'cifs_srv_smb_options': '',
            'cifs_srv_timeserver': False,
            'cifs_srv_unixcharset': 'UTF-8',
            'cifs_srv_unixext': True,
            'cifs_srv_workgroup': '',
            'cifs_srv_zeroconf': True
        })

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
        self.assertHttpOK(resp)
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
        self.assertEqual(data, {
            'id': obj.id,
            'ddns_domain': '',
            'ddns_fupdateperiod': '',
            'ddns_ipserver': '',
            'ddns_options': '',
            'ddns_password': '',
            'ddns_provider': 'dyndns@dyndns.org',
            'ddns_updateperiod': '',
            'ddns_username': '',
        })

    def test_Update(self):
        obj = models.DynamicDNS.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'ddns_username': 'testuser',
                'ddns_password': 'mypass',
            }
        )
        self.assertHttpOK(resp)
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
        self.assertEqual(data, {
            'id': obj.id,
            'ftp_anonpath': None,
            'ftp_anonuserbw': 0,
            'ftp_anonuserdlbw': 0,
            'ftp_banner': '',
            'ftp_clients': 32,
            'ftp_defaultroot': False,
            'ftp_dirmask': '077',
            'ftp_filemask': '077',
            'ftp_fxp': False,
            'ftp_ident': False,
            'ftp_ipconnections': 0,
            'ftp_localuserbw': 0,
            'ftp_localuserdlbw': 0,
            'ftp_loginattempt': 3,
            'ftp_masqaddress': '',
            'ftp_onlyanonymous': False,
            'ftp_onlylocal': False,
            'ftp_options': '',
            'ftp_passiveportsmax': 0,
            'ftp_passiveportsmin': 0,
            'ftp_port': 21,
            'ftp_resume': False,
            'ftp_reversedns': False,
            'ftp_rootlogin': False,
            'ftp_ssltls_certfile': '',
            'ftp_timeout': 120,
            'ftp_tls': False,
            'ftp_tls_opt_allow_client_renegotiations': False,
            'ftp_tls_opt_allow_dot_login': False,
            'ftp_tls_opt_allow_per_user': False,
            'ftp_tls_opt_common_name_required': False,
            'ftp_tls_opt_dns_name_required': False,
            'ftp_tls_opt_enable_diags': False,
            'ftp_tls_opt_export_cert_data': False,
            'ftp_tls_opt_ip_address_required': False,
            'ftp_tls_opt_no_cert_request': False,
            'ftp_tls_opt_no_empty_fragments': False,
            'ftp_tls_opt_no_session_reuse_required': False,
            'ftp_tls_opt_stdenvvars': False,
            'ftp_tls_opt_use_implicit_ssl': False,
            'ftp_tls_policy': 'on'
        })

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
        self.assertHttpOK(resp)
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


class LLDPResourceTest(APITestCase):

    def setUp(self):
        super(LLDPResourceTest, self).setUp()
        models.services.objects.create(
            srv_service='lldp',
        )
        self._obj = models.LLDP.objects.create()

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
            'lldp_intdesc': True,
            'lldp_country': '',
            'lldp_location': '',
        })

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'lldp_intdesc': False,
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._obj.id)
        self.assertEqual(data['lldp_intdesc'], False)

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
        self.assertEqual(data, {
            'id': obj.id,
            'nfs_srv_allow_nonroot': False,
            'nfs_srv_bindip': '',
            'nfs_srv_mountd_port': None,
            'nfs_srv_rpclockd_port': None,
            'nfs_srv_rpcstatd_port': None,
            'nfs_srv_servers': 4,
            'nfs_srv_udp': False,
            'nfs_srv_v4': False
        })

    def test_Update(self):
        obj = models.NFS.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'nfs_srv_servers': 10,
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['nfs_srv_servers'], 10)

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
        self.assertEqual(data, {
            'id': obj.id,
            'rsyncd_auxiliary': '',
            'rsyncd_port': 873
        })

    def test_Update(self):
        obj = models.Rsyncd.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'rsyncd_port': 874,
            }
        )
        self.assertHttpOK(resp)
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
            'id': 1,
            'rsyncmod_auxiliary': '',
            'rsyncmod_comment': '',
            'rsyncmod_group': 'nobody',
            'rsyncmod_hostsallow': '',
            'rsyncmod_hostsdeny': '',
            'rsyncmod_maxconn': 0,
            'rsyncmod_mode': 'rw',
            'rsyncmod_name': 'testmod',
            'rsyncmod_path': '/mnt/tank',
            'rsyncmod_user': 'nobody'
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
            'id': obj.id,
            'rsyncmod_auxiliary': '',
            'rsyncmod_comment': '',
            'rsyncmod_group': 'nobody',
            'rsyncmod_hostsallow': '',
            'rsyncmod_hostsdeny': '',
            'rsyncmod_maxconn': 0,
            'rsyncmod_mode': 'rw',
            'rsyncmod_name': 'testmod',
            'rsyncmod_path': '/mnt/tank',
            'rsyncmod_user': 'nobody'
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
        self.assertHttpOK(resp)
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
        self.assertEqual(data, [{
            'srv_service': 'ftp', 'srv_enable': False, 'id': 1,
        }])

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
            data={
                'srv_enable': True,
            }
        )
        self.assertHttpOK(resp)
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
        self.assertEqual(data, {
            'id': obj.id,
            'smart_critical': 0,
            'smart_difference': 0,
            'smart_email': '',
            'smart_informational': 0,
            'smart_interval': 30,
            'smart_powermode': 'never'
        })

    def test_Update(self):
        obj = models.SMART.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'smart_interval': 40,
            }
        )
        self.assertHttpOK(resp)
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
        self.assertEqual(data, {
            'id': obj.id,
            'snmp_community': 'public',
            'snmp_contact': '',
            'snmp_location': '',
            'snmp_options': '',
            'snmp_traps': False
        })

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
        self.assertHttpOK(resp)
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
        self.assertEqual(data, {
            'id': obj.id,
            'ssh_compression': False,
            'ssh_host_dsa_key': '',
            'ssh_host_dsa_key_pub': '',
            'ssh_host_ecdsa_key': '',
            'ssh_host_ecdsa_key_pub': '',
            'ssh_host_key': '',
            'ssh_host_key_pub': '',
            'ssh_host_rsa_key': '',
            'ssh_host_rsa_key_pub': '',
            'ssh_options': '',
            'ssh_passwordauth': False,
            'ssh_privatekey': '',
            'ssh_rootlogin': False,
            'ssh_sftp_log_facility': '',
            'ssh_sftp_log_level': '',
            'ssh_tcpfwd': False,
            'ssh_tcpport': 22
        })

    def test_Update(self):
        obj = models.SSH.objects.create()
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'ssh_tcpfwd': True,
            }
        )
        self.assertHttpOK(resp)
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
        self.assertEqual(data, {
            'id': obj.id,
            'tftp_directory': '',
            'tftp_newfiles': False,
            'tftp_options': '',
            'tftp_port': 69,
            'tftp_umask': '022',
            'tftp_username': 'nobody'
        })

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
        self.assertHttpOK(resp)
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
            iscsi_basename='iqn.2005-10.org.freenas.ctl',
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
        self.assertEqual(data, {
            'id': self._obj.id,
            'iscsi_basename': 'iqn.2005-10.org.freenas.ctl',
            'iscsi_discoveryauthgroup': None,
            'iscsi_discoveryauthmethod': 'Auto'
        })

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'iscsi_basename': "iqn.2005-10.org.freenas.ctl",
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._obj.id)
        self.assertEqual(data['iscsi_basename'], "iqn.2005-10.org.freenas.ctl")

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
            'id': 1,
            'iscsi_target_extent_comment': '',
            'iscsi_target_extent_filesize': '10MB',
            'iscsi_target_extent_insecure_tpc': True,
            'iscsi_target_extent_naa': '0x3424a029e4881552',
            'iscsi_target_extent_name': 'extent',
            'iscsi_target_extent_path': '/mnt/tank/iscsi',
            'iscsi_target_extent_type': 'File'
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
            'id': obj.id,
            'iscsi_target_extent_comment': '',
            'iscsi_target_extent_filesize': '10MB',
            'iscsi_target_extent_insecure_tpc': True,
            'iscsi_target_extent_naa': '',
            'iscsi_target_extent_name': 'extent',
            'iscsi_target_extent_path': '/mnt/tank/iscsi',
            'iscsi_target_extent_type': 'File'
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
        self.assertHttpOK(resp)
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
            'id': 1,
            'iscsi_target_initiator_auth_network': 'ALL',
            'iscsi_target_initiator_comment': '',
            'iscsi_target_initiator_initiators': 'ALL',
            'iscsi_target_initiator_tag': 1
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
            'id': obj.id,
            'iscsi_target_initiator_auth_network': 'ALL',
            'iscsi_target_initiator_comment': '',
            'iscsi_target_initiator_initiators': 'ALL',
            'iscsi_target_initiator_tag': 1
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
        self.assertHttpOK(resp)
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
            'id': 1,
            'iscsi_target_auth_peersecret': 'peersecret',
            'iscsi_target_auth_peeruser': 'peeruser',
            'iscsi_target_auth_secret': 'secret',
            'iscsi_target_auth_tag': 1,
            'iscsi_target_auth_user': 'user'
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
            'id': obj.id,
            'iscsi_target_auth_peersecret': 'peersecret',
            'iscsi_target_auth_peeruser': 'peeruser',
            'iscsi_target_auth_secret': 'secret',
            'iscsi_target_auth_tag': 1,
            'iscsi_target_auth_user': 'user'
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
        self.assertHttpOK(resp)
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
            'id': 1,
            'iscsi_target_alias': None,
            'iscsi_target_authgroup': None,
            'iscsi_target_authtype': 'Auto',
            'iscsi_target_initialdigest': 'Auto',
            'iscsi_target_initiatorgroup': 1,
            'iscsi_target_logical_blocksize': 512,
            'iscsi_target_name': 'target',
            'iscsi_target_portalgroup': 1,
            'iscsi_target_serial': '10000001',
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
            'id': obj.id,
            'iscsi_target_alias': None,
            'iscsi_target_authgroup': None,
            'iscsi_target_authtype': 'Auto',
            'iscsi_target_initialdigest': 'Auto',
            'iscsi_target_initiatorgroup': 1,
            'iscsi_target_logical_blocksize': 512,
            'iscsi_target_name': 'target',
            'iscsi_target_portalgroup': 1,
            'iscsi_target_serial': '10000001',
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
                'iscsi_target_alias': "test",
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['iscsi_target_alias'], "test")

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
            'id': 1,
            'iscsi_extent': 1,
            'iscsi_lunid': None,
            'iscsi_target': 1,
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
            'id': obj.id,
            'iscsi_extent': 1,
            'iscsi_lunid': None,
            'iscsi_target': 1,
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
                'iscsi_target_alias': "test",
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['iscsi_target_alias'], "test")

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
            'id': 1,
            'iscsi_target_portal_comment': 'comment',
            'iscsi_target_portal_ips': ['0.0.0.0:3260'],
            'iscsi_target_portal_tag': 1
        })

    def test_Retrieve(self):
        obj = models.iSCSITargetPortal.objects.create()
        models.iSCSITargetPortalIP.objects.create(
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
            'id': obj.id,
            'iscsi_target_portal_comment': '',
            'iscsi_target_portal_ips': ['0.0.0.0:3260'],
            'iscsi_target_portal_tag': 1
        }])

    def test_Update(self):
        obj = models.iSCSITargetPortal.objects.create()
        models.iSCSITargetPortalIP.objects.create(
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
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['iscsi_target_portal_comment'], 'comment2')
        self.assertEqual(data['iscsi_target_portal_ips'], ['0.0.0.0:3261'])

    def test_Delete(self):
        obj = models.iSCSITargetPortal.objects.create()
        models.iSCSITargetPortalIP.objects.create(
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
        self.assertEqual(data, {
            'id': self._obj.id,
            'ups_description': '',
            'ups_driver': '',
            'ups_emailnotify': False,
            'ups_extrausers': '',
            'ups_identifier': 'ups',
            'ups_mode': 'master',
            'ups_monpwd': 'fixmepass',
            'ups_monuser': 'upsmon',
            'ups_options': '',
            'ups_port': '',
            'ups_remotehost': '',
            'ups_remoteport': 3493,
            'ups_rmonitor': False,
            'ups_shutdown': 'batt',
            'ups_shutdowntimer': 30,
            'ups_subject': 'UPS report generated by %h',
            'ups_toemail': ''
        })

    def test_Update(self):
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), self._obj.id),
            format='json',
            data={
                'ups_rmonitor': True,
                'ups_port': '/mnt/tank/ups',
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], self._obj.id)
        self.assertEqual(data['ups_rmonitor'], True)

    def test_Delete(self):
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), 1),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)
