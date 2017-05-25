# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.api.tests.utils import APITestCase
from freenasUI.middleware.notifier import notifier
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
            'disk_acousticlevel': 'Disabled',
            'disk_advpowermgmt': 'Disabled',
            'disk_description': '',
            'disk_expiretime': None,
            'disk_hddstandby': 'Always On',
            'disk_identifier': '',
            'disk_multipath_member': '',
            'disk_multipath_name': '',
            'disk_name': 'ada1',
            'disk_serial': '',
            'disk_size': '',
            'disk_smartoptions': '',
            'disk_togglesmart': True,
            'disk_transfermode': 'Auto',
            'id': obj.id,
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
        self.assertHttpOK(resp)
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

    def test_Replace_Disk(self):

        pool = notifier().zpool_parse('tankpool')
        devs = pool.get_devs()

        resp = self.api_client.post(
            '%s1/replace/' % self.get_api_url(),
            format='json',
            data={
                'label': devs[0].name,
                'replace_disk': 'ada6',
            }
        )
        self.assertHttpAccepted(resp)

    def test_Offline_Disk(self):

        pool = notifier().zpool_parse('tankpool')
        devs = pool.get_devs()

        resp = self.api_client.post(
            '%s1/offline/' % self.get_api_url(),
            format='json',
            data={
                'label': devs[0].name,
            }
        )
        self.assertHttpAccepted(resp)

    def test_Detach_Disk(self):

        pool = notifier().zpool_parse('tankpool')
        devs = pool.get_devs()

        resp = self.api_client.post(
            '%s1/detach/' % self.get_api_url(),
            format='json',
            data={
                'label': devs[0].name,
            }
        )
        self.assertHttpAccepted(resp)


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
            'id': 1,
            'scrub_daymonth': '*',
            'scrub_dayweek': '7',
            'scrub_description': '',
            'scrub_enabled': True,
            'scrub_hour': '00',
            'scrub_minute': '00',
            'scrub_month': '*',
            'scrub_threshold': 35,
            'scrub_volume': 'tank',
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
            'id': obj.id,
            'scrub_daymonth': '*',
            'scrub_dayweek': '7',
            'scrub_description': '',
            'scrub_enabled': True,
            'scrub_hour': '00',
            'scrub_minute': '00',
            'scrub_month': '*',
            'scrub_threshold': 35,
            'scrub_volume': 'tank'
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
        self.assertHttpOK(resp)
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
            'id': 1,
            'task_begin': '09:00:00',
            'task_byweekday': '1,2,3,4,5',
            'task_enabled': True,
            'task_end': '18:00:00',
            'task_filesystem': 'tank',
            'task_interval': 60,
            'task_recursive': False,
            'task_repeat_unit': 'weekly',
            'task_ret_count': 2,
            'task_ret_unit': 'week',
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
            'id': obj.id,
            'task_begin': '09:00:00',
            'task_byweekday': '1,2,3,4,5',  #FIXME: array
            'task_enabled': True,
            'task_end': '18:00:00',
            'task_filesystem': 'tank',
            'task_interval': 60,
            'task_recursive': False,
            'task_repeat_unit': 'weekly',
            'task_ret_count': 2,
            'task_ret_unit': 'week',
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
        self.assertHttpOK(resp)
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
            'id': 1,
            'repl_begin': '00:00:00',
            'repl_enabled': True,
            'repl_end': '23:59:00',
            'repl_filesystem': 'tank',
            'repl_lastsnapshot': '',
            'repl_limit': 0,
            'repl_userepl': False,
            'repl_zfs': 'tank',
            'repl_remote_dedicateduser': None,
            'repl_remote_dedicateduser_enabled': False,
            'repl_remote_cipher': 'standard',
            'repl_remote_hostkey': 'AAAA',
            'repl_remote_hostname': 'testhost',
            'repl_remote_port': 22,
            'repl_compression': 'lz4',
            'repl_status': 'Waiting',
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
            'id': obj.id,
            'repl_begin': '00:00:00',
            'repl_enabled': True,
            'repl_end': '23:59:00',
            'repl_filesystem': 'tank',
            'repl_lastsnapshot': '',
            'repl_limit': 0,
            'repl_userepl': False,
            'repl_zfs': 'tank',
            'repl_remote_dedicateduser': None,
            'repl_remote_dedicateduser_enabled': False,
            'repl_remote_cipher': 'standard',
            'repl_remote_hostkey': 'AAAA',
            'repl_remote_hostname': 'testhost',
            'repl_remote_port': 22,
            'repl_compression': 'lz4',
            'repl_status': 'Waiting',
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
        self.assertHttpOK(resp)
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
