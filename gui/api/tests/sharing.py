from .utils import APITestCase
from freenasUI.sharing import models
from freenasUI.storage.models import MountPoint, Volume


class CommonMixin(object):

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


class CIFS_ShareResourceTest(CommonMixin, APITestCase):

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
            u'cifs_browsable': False,
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
            cifs_path='/mnt/',
            cifs_guestok=True,
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                u'cifs_guestonly': True,
                u'cifs_name': u'test share',
                u'cifs_path': u'/mnt/tank',
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
