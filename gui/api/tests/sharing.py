from .utils import APITestCase
from freenasUI.sharing import models
from freenasUI.storage.models import MountPoint, Volume


class CommonMixin(object):

    maxDiff = None

    def setUp(self):
        super(CommonMixin, self).setUp()
        v = Volume.objects.create(
            vol_name='tank',
            vol_fstype='ZFS',
        )
        MountPoint.objects.create(
            mp_path='/mnt/tank',
            mp_volume=v,
        )


class CIFSResourceTest(CommonMixin, APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                u'cifs_guestonly': True,
                u'cifs_name': u'test share',
                u'cifs_path': u'/mnt/tank/',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'cifs_name': u'test share',
            u'cifs_comment': u'',
            u'cifs_path': u'/mnt/tank',
            u'cifs_guestok': False,
            u'cifs_guestonly': True,
            u'cifs_hostsallow': u'',
            u'cifs_hostsdeny': u'',
            u'cifs_inheritowner': False,
            u'cifs_inheritperms': False,
            u'cifs_recyclebin': False,
            u'cifs_ro': False,
            u'cifs_showhiddenfiles': False,
            u'cifs_auxsmbconf': u'',
            u'cifs_browsable': True,
        })

    def test_Retrieve(self):
        obj = models.CIFS_Share.objects.create(
            cifs_name='test share',
            cifs_comment='comment',
            cifs_path='/mnt/',
            cifs_guestok=True,
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [
            {
                u'id': obj.id,
                u'cifs_name': u'test share',
                u'cifs_comment': u'comment',
                u'cifs_path': u'/mnt/',
                u'cifs_guestok': True,
                u'cifs_guestonly': False,
                u'cifs_hostsallow': u'',
                u'cifs_hostsdeny': u'',
                u'cifs_inheritowner': False,
                u'cifs_inheritperms': False,
                u'cifs_recyclebin': False,
                u'cifs_ro': False,
                u'cifs_showhiddenfiles': False,
                u'cifs_auxsmbconf': u'',
                u'cifs_browsable': True,
            }
        ])

    def test_Update(self):
        obj = models.CIFS_Share.objects.create(
            cifs_name='test share',
            cifs_comment='comment',
            cifs_path='/mnt/tank',
            cifs_guestok=True,
            cifs_guestonly=False,
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                u'cifs_guestonly': True,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['cifs_guestonly'], True)

    def test_Delete(self):
        obj = models.CIFS_Share.objects.create(
            cifs_name='test share',
            cifs_comment='comment',
            cifs_path='/mnt/',
            cifs_guestok=True,
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class AFPResourceTest(CommonMixin, APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                u'afp_name': u'test share',
                u'afp_path': u'/mnt/tank',
                u'afp_discoverymode': u'default',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'afp_adouble': True,
            u'afp_allow': u'',
            u'afp_cachecnid': False,
            u'afp_comment': u'',
            u'afp_crlf': False,
            u'afp_dbpath': u'',
            u'afp_deny': u'',
            u'afp_discoverymode': u'default',
            u'afp_diskdiscovery': False,
            u'afp_dperm': u'644',
            u'afp_fperm': u'755',
            u'afp_mswindows': False,
            u'afp_name': u'test share',
            u'afp_nodev': False,
            u'afp_nofileid': False,
            u'afp_nohex': False,
            u'afp_nostat': False,
            u'afp_path': u'/mnt/tank',
            u'afp_prodos': False,
            u'afp_ro': u'',
            u'afp_rw': u'',
            u'afp_sharecharset': u'',
            u'afp_sharepw': u'',
            u'afp_upriv': True,
        })

    def test_Retrieve(self):
        obj = models.AFP_Share.objects.create(
            afp_name='test share',
            afp_path='/mnt/tank',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'afp_adouble': True,
            u'afp_allow': u'',
            u'afp_cachecnid': False,
            u'afp_comment': u'',
            u'afp_crlf': False,
            u'afp_dbpath': u'',
            u'afp_deny': u'',
            u'afp_discoverymode': u'default',
            u'afp_diskdiscovery': False,
            u'afp_dperm': u'644',
            u'afp_fperm': u'755',
            u'afp_mswindows': False,
            u'afp_name': u'test share',
            u'afp_nodev': False,
            u'afp_nofileid': False,
            u'afp_nohex': False,
            u'afp_nostat': False,
            u'afp_path': u'/mnt/tank',
            u'afp_prodos': False,
            u'afp_ro': u'',
            u'afp_rw': u'',
            u'afp_sharecharset': u'',
            u'afp_sharepw': u'',
            u'afp_upriv': True,
        }])

    def test_Update(self):
        obj = models.AFP_Share.objects.create(
            afp_name='test share',
            afp_path='/mnt/tank',
            afp_upriv=True,
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                u'afp_upriv': False,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['afp_upriv'], False)

    def test_Delete(self):
        obj = models.AFP_Share.objects.create()
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class NFSResourceTest(CommonMixin, APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                u'nfs_comment': u'test share',
                u'nfs_paths': [u'/mnt/tank'],
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'nfs_comment': u'test share',
            u'nfs_hosts': u'',
            u'nfs_mapall_group': u'',
            u'nfs_mapall_user': u'',
            u'nfs_maproot_group': u'',
            u'nfs_maproot_user': u'',
            u'nfs_network': u'',
            u'nfs_paths': [u'/mnt/tank'],
            u'nfs_alldirs': False,
            u'nfs_quiet': False,
            u'nfs_ro': False
        })

    def test_Retrieve(self):
        obj = models.NFS_Share.objects.create(
            nfs_comment='test share',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'nfs_alldirs': False,
            u'nfs_comment': u'test share',
            u'nfs_hosts': u'',
            u'nfs_mapall_group': u'',
            u'nfs_mapall_user': u'',
            u'nfs_maproot_group': u'',
            u'nfs_maproot_user': u'',
            u'nfs_network': u'',
            u'nfs_paths': [],
            u'nfs_quiet': False,
            u'nfs_ro': False
        }])

    def test_Update(self):
        obj = models.NFS_Share.objects.create(
            nfs_comment='test share',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                u'nfs_ro': True,
                u'nfs_paths': [u'/mnt/tank'],  #FIXME: nfs paths validation
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['nfs_ro'], True)

    def test_Delete(self):
        obj = models.NFS_Share.objects.create()
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)
