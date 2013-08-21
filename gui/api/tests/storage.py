from .utils import APITestCase
from freenasUI.storage import models


class DiskResourceTest(APITestCase):

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)

    def test_Retrieve(self):
        obj = models.Disk.objects.create(
            disk_name='ada1',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'disk_acousticlevel': u'Disabled',
            u'disk_advpowermgmt': u'Disabled',
            u'disk_description': u'',
            u'disk_enabled': True,
            u'disk_hddstandby': u'Always On',
            u'disk_identifier': u'',
            u'disk_multipath_member': u'',
            u'disk_multipath_name': u'',
            u'disk_name': u'ada1',
            u'disk_serial': u'',
            u'disk_smartoptions': u'',
            u'disk_togglesmart': True,
            u'disk_transfermode': u'Auto',
            u'id': obj.id,
        }])

    def test_Update(self):
        obj = models.Disk.objects.create(
            disk_name='ada1',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'disk_description': 'test',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['disk_description'], 'test')

    def test_Delete(self):
        obj = models.Disk.objects.create(
            disk_name='ada1',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpMethodNotAllowed(resp)


class VolumeResourceTest(APITestCase):

    def setUp(self):
        super(VolumeResourceTest, self).setUp()
        self._create_zpool()

    def tearDown(self):
        super(VolumeResourceTest, self).tearDown()
        self._delete_zpool()

    def _create_zpool(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'volume_name': 'tankpool',
                'layout': [
                    {
                        'vdevtype': 'mirror',
                        'disks': ['ada4', 'ada5'],  # FIXME: use right disks
                    }
                ],
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data['children'], [])
        self.assertEqual(data['status'], "HEALTHY")
        self.assertEqual(data['vol_name'], "tankpool")
        self.assertEqual(data['vol_fstype'], "ZFS")
        self.assertEqual(data['vol_encrypt'], 0)
        self.assertEqual(data['mountpoint'], '/mnt/tankpool')

    def _delete_zpool(self):
        resp = self.api_client.delete(
            '%s1/' % self.get_api_url(),
        )
        self.assertHttpAccepted(resp)

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )


class ScrubResourceTest(APITestCase):

    def setUp(self):
        super(ScrubResourceTest, self).setUp()
        self._vol = models.Volume.objects.create(
            vol_name='tank',
            vol_fstype='ZFS',
        )
        models.MountPoint.objects.create(
            mp_path='/mnt/tank',
            mp_volume=self._vol,
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
                'scrub_volume': self._vol.id,
                'scrub_minute': '00',
                'scrub_hour': '00',
                'scrub_daymonth': '*',
                'scrub_month': '*',
                'scrub_dayweek': '7',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'scrub_daymonth': u'*',
            u'scrub_dayweek': u'7',
            u'scrub_description': u'',
            u'scrub_enabled': True,
            u'scrub_hour': u'00',
            u'scrub_minute': u'00',
            u'scrub_month': u'*',
            u'scrub_threshold': 35,
            u'scrub_volume': u'tank',
            u'scrub_volume_id': None,
        })

    def test_Retrieve(self):
        obj = models.Scrub.objects.create(
            scrub_volume=self._vol
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'scrub_daymonth': u'*',
            u'scrub_dayweek': u'7',
            u'scrub_description': u'',
            u'scrub_enabled': True,
            u'scrub_hour': u'00',
            u'scrub_minute': u'00',
            u'scrub_month': u'*',
            u'scrub_threshold': 35,
            u'scrub_volume': u'tank'
        }])

    def test_Update(self):
        obj = models.Scrub.objects.create(
            scrub_volume=self._vol,
            scrub_enabled=True,
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'scrub_enabled': False,
                'scrub_volume': obj.id,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['scrub_enabled'], False)

    def test_Delete(self):
        obj = models.Scrub.objects.create(
            scrub_volume=self._vol,
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class TaskResourceTest(APITestCase):

    def setUp(self):
        super(TaskResourceTest, self).setUp()
        self._vol = models.Volume.objects.create(
            vol_name='tank',
            vol_fstype='ZFS',
        )
        models.MountPoint.objects.create(
            mp_path='/mnt/tank',
            mp_volume=self._vol,
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
                'task_filesystem': 'tank',
                'task_recursive': False,
                'task_ret_unit': 'week',
                'task_interval': 60,
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'task_begin': u'09:00:00',
            u'task_byweekday': u'1,2,3,4,5',
            u'task_enabled': True,
            u'task_end': u'18:00:00',
            u'task_filesystem': u'tank',
            u'task_interval': 60,
            u'task_recursive': False,
            u'task_repeat_unit': u'weekly',
            u'task_ret_count': 2,
            u'task_ret_unit': u'week',
        })

    def test_Retrieve(self):
        obj = models.Task.objects.create(
            task_filesystem='tank',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'task_begin': u'09:00:00',
            u'task_byweekday': u'1,2,3,4,5',  #FIXME: array
            u'task_enabled': True,
            u'task_end': u'18:00:00',
            u'task_filesystem': u'tank',
            u'task_interval': 60,
            u'task_recursive': False,
            u'task_repeat_unit': u'weekly',
            u'task_ret_count': 2,
            u'task_ret_unit': u'week',
        }])

    def test_Update(self):
        obj = models.Task.objects.create(
            task_filesystem='tank',
            task_enabled=True,
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'task_enabled': False,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['task_enabled'], False)

    def test_Delete(self):
        obj = models.Task.objects.create(
            task_filesystem='tank',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class ReplicationResourceTest(APITestCase):

    def setUp(self):
        super(ReplicationResourceTest, self).setUp()
        self._vol = models.Volume.objects.create(
            vol_name='tank',
            vol_fstype='ZFS',
        )
        models.MountPoint.objects.create(
            mp_path='/mnt/tank',
            mp_volume=self._vol,
        )
        self._task = models.Task.objects.create(
            task_filesystem='tank',
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
                'repl_filesystem': 'tank',
                'repl_zfs': 'tank',
                'repl_remote_hostname': 'testhost',
                'repl_remote_hostkey': 'AAAA',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'repl_begin': u'00:00:00',
            u'repl_enabled': True,
            u'repl_end': u'23:59:00',
            u'repl_filesystem': u'tank',
            u'repl_lastsnapshot': u'',
            u'repl_limit': 0,
            u'repl_resetonce': False,
            u'repl_userepl': False,
            u'repl_zfs': u'tank',
            u'repl_remote_dedicateduser': None,
            u'repl_remote_dedicateduser_enabled': False,
            u'repl_remote_fast_cipher': False,
            u'repl_remote_hostkey': u'AAAA',
            u'repl_remote_hostname': u'testhost',
            u'repl_remote_port': 22,
        })

    def test_Retrieve(self):
        remote = models.ReplRemote.objects.create(
            ssh_remote_hostname='testhost',
            ssh_remote_hostkey='AAAA',
            ssh_remote_dedicateduser=None,
        )
        obj = models.Replication.objects.create(
            repl_filesystem='tank',
            repl_zfs='tank',
            repl_remote=remote,
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            u'id': obj.id,
            u'repl_begin': u'00:00:00',
            u'repl_enabled': True,
            u'repl_end': u'23:59:00',
            u'repl_filesystem': u'tank',
            u'repl_lastsnapshot': u'',
            u'repl_limit': 0,
            u'repl_resetonce': False,
            u'repl_userepl': False,
            u'repl_zfs': u'tank',
            u'repl_remote_dedicateduser': None,
            u'repl_remote_dedicateduser_enabled': False,
            u'repl_remote_fast_cipher': False,
            u'repl_remote_hostkey': u'AAAA',
            u'repl_remote_hostname': u'testhost',
            u'repl_remote_port': 22,
        }])

    def test_Update(self):
        remote = models.ReplRemote.objects.create(
            ssh_remote_hostname='testhost',
            ssh_remote_hostkey='AAAA',
        )
        obj = models.Replication.objects.create(
            repl_filesystem='tank',
            repl_zfs='tank',
            repl_userepl=False,
            repl_remote=remote,
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'repl_userepl': True,
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['repl_userepl'], True)

    def test_Delete(self):
        remote = models.ReplRemote.objects.create(
            ssh_remote_hostname='testhost',
            ssh_remote_hostkey='AAAA',
        )
        obj = models.Replication.objects.create(
            repl_filesystem='tank',
            repl_zfs='tank',
            repl_remote=remote,
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)
