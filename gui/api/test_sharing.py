# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.api.tests.utils import APITestCase
from freenasUI.sharing import models
from freenasUI.storage.models import MountPoint, Volume


class CommonMixin(object):

    maxDiff = None

    def setUp(self):
        super(CommonMixin, self).setUp()
        v = Volume.objects.create(
            vol_name='tank',
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
                'cifs_guestonly': True,
                'cifs_name': 'test share',
                'cifs_path': '/mnt/tank/',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            'id': 1,
            'cifs_name': 'test share',
            'cifs_comment': '',
            'cifs_path': '/mnt/tank',
            'cifs_default_permissions': True,
            'cifs_guestok': False,
            'cifs_guestonly': True,
            'cifs_hostsallow': '',
            'cifs_hostsdeny': '',
            'cifs_recyclebin': False,
            'cifs_ro': False,
            'cifs_showhiddenfiles': False,
            'cifs_auxsmbconf': '',
            'cifs_browsable': True,
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
                'id': obj.id,
                'cifs_name': 'test share',
                'cifs_comment': 'comment',
                'cifs_path': '/mnt/',
                'cifs_default_permissions': True,
                'cifs_guestok': True,
                'cifs_guestonly': False,
                'cifs_hostsallow': '',
                'cifs_hostsdeny': '',
                'cifs_recyclebin': False,
                'cifs_ro': False,
                'cifs_showhiddenfiles': False,
                'cifs_auxsmbconf': '',
                'cifs_browsable': True,
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
                'cifs_guestonly': True,
            }
        )
        self.assertHttpOK(resp)
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
                'afp_name': 'test share',
                'afp_path': '/mnt/tank',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            'id': 1,
            'afp_allow': '',
            'afp_comment': '',
            'afp_deny': '',
            'afp_dperm': '755',
            'afp_fperm': '644',
            'afp_name': 'test share',
            'afp_nodev': False,
            'afp_nostat': False,
            'afp_path': '/mnt/tank',
            'afp_ro': '',
            'afp_rw': '',
            'afp_timemachine': False,
            'afp_umask': '000',
            'afp_upriv': True,
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
            'id': obj.id,
            'afp_allow': '',
            'afp_comment': '',
            'afp_deny': '',
            'afp_dperm': '755',
            'afp_fperm': '644',
            'afp_name': 'test share',
            'afp_nodev': False,
            'afp_nostat': False,
            'afp_path': '/mnt/tank',
            'afp_ro': '',
            'afp_rw': '',
            'afp_timemachine': False,
            'afp_umask': '000',
            'afp_upriv': True,
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
                'afp_upriv': False,
            }
        )
        self.assertHttpOK(resp)
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
                'nfs_comment': 'test share',
                'nfs_paths': ['/mnt/tank'],
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            'id': 1,
            'nfs_comment': 'test share',
            'nfs_hosts': '',
            'nfs_mapall_group': '',
            'nfs_mapall_user': '',
            'nfs_maproot_group': '',
            'nfs_maproot_user': '',
            'nfs_network': '',
            'nfs_paths': ['/mnt/tank'],
            'nfs_alldirs': False,
            'nfs_quiet': False,
            'nfs_ro': False,
            'nfs_security': []
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
            'id': obj.id,
            'nfs_alldirs': False,
            'nfs_comment': 'test share',
            'nfs_hosts': '',
            'nfs_mapall_group': '',
            'nfs_mapall_user': '',
            'nfs_maproot_group': '',
            'nfs_maproot_user': '',
            'nfs_network': '',
            'nfs_paths': [],
            'nfs_quiet': False,
            'nfs_ro': False,
            'nfs_security': []
        }])

    def test_Update(self):
        obj = models.NFS_Share.objects.create(
            nfs_comment='test share',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'nfs_ro': True,
                'nfs_paths': ['/mnt/tank'],  #FIXME: nfs paths validation
            }
        )
        self.assertHttpOK(resp)
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
