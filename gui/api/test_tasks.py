# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.api.tests.utils import APITestCase
from freenasUI.storage.models import Disk, MountPoint, Volume
from freenasUI.tasks import models


class CronJobResourceTest(APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'cron_user': 'root',
                'cron_command': 'ls /',
                'cron_minute': '*/20',
                'cron_hour': '*',
                'cron_daymonth': '*',
                'cron_month': '*',
                'cron_dayweek': '*',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            'id': 1,
            'cron_command': 'ls /',
            'cron_daymonth': '*',
            'cron_dayweek': '*',
            'cron_description': '',
            'cron_enabled': True,
            'cron_hour': '*',
            'cron_minute': '*/20',
            'cron_month': '*',
            'cron_stderr': False,
            'cron_stdout': True,
            'cron_user': 'root',
        })

    def test_Retrieve(self):
        obj = models.CronJob.objects.create(
            cron_user='root',
            cron_command='ls /',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            'id': obj.id,
            'cron_command': 'ls /',
            'cron_daymonth': '*',
            'cron_dayweek': '*',
            'cron_description': '',
            'cron_enabled': True,
            'cron_hour': '*',
            'cron_minute': '00',
            'cron_month': '*',
            'cron_stderr': False,
            'cron_stdout': True,
            'cron_user': 'root',
        }])

    def test_Update(self):
        obj = models.CronJob.objects.create(
            cron_user='root',
            cron_command='ls /',
            cron_dayweek='*',
            cron_stdout=True,
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'cron_dayweek': '1,2',
                'cron_stdout': False,
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['cron_dayweek'], '1,2')
        self.assertEqual(data['cron_stdout'], False)

    def test_Delete(self):
        obj = models.CronJob.objects.create(
            cron_user='root',
            cron_command='ls /',
            cron_dayweek='*',
            cron_stdout=True,
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class InitShutdownResourceTest(APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'ini_type': 'command',
                'ini_command': 'echo "init" > /tmp/init',
                'ini_when': 'postinit',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            'id': 1,
            'ini_command': 'echo "init" > /tmp/init',
            'ini_script': None,
            'ini_type': 'command',
            'ini_when': 'postinit'
        })

    def test_Retrieve(self):
        obj = models.InitShutdown.objects.create(
            ini_type='command',
            ini_command='echo "init" > /tmp/init',
            ini_when='postinit',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            'id': obj.id,
            'ini_command': 'echo "init" > /tmp/init',
            'ini_script': None,
            'ini_type': 'command',
            'ini_when': 'postinit'
        }])

    def test_Update(self):
        obj = models.InitShutdown.objects.create(
            ini_type='command',
            ini_command='echo "init" > /tmp/init',
            ini_when='postinit',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'ini_when': 'preinit',
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['ini_when'], 'preinit')

    def test_Delete(self):
        obj = models.InitShutdown.objects.create(
            ini_type='command',
            ini_command='echo "init" > /tmp/init',
            ini_when='postinit',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class RsyncResourceTest(APITestCase):

    def setUp(self):
        super(RsyncResourceTest, self).setUp()
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
                'rsync_path': '/mnt/tank',
                'rsync_user': 'root',
                'rsync_mode': 'module',
                'rsync_remotemodule': 'testmodule',
                'rsync_remotehost': 'testhost',
                'rsync_direction': 'push',
                'rsync_minute': '*/20',
                'rsync_hour': '*',
                'rsync_daymonth': '*',
                'rsync_month': '*',
                'rsync_dayweek': '*',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            'id': 1,
            'rsync_archive': False,
            'rsync_compress': True,
            'rsync_daymonth': '*',
            'rsync_dayweek': '*',
            'rsync_delete': False,
            'rsync_desc': '',
            'rsync_direction': 'push',
            'rsync_enabled': True,
            'rsync_extra': '',
            'rsync_hour': '*',
            'rsync_minute': '*/20',
            'rsync_mode': 'module',
            'rsync_month': '*',
            'rsync_path': '/mnt/tank',
            'rsync_preserveattr': False,
            'rsync_preserveperm': False,
            'rsync_quiet': False,
            'rsync_recursive': True,
            'rsync_remotehost': 'testhost',
            'rsync_remotemodule': 'testmodule',
            'rsync_remotepath': '',
            'rsync_remoteport': 22,
            'rsync_times': True,
            'rsync_user': 'root'
        })

    def test_Retrieve(self):
        obj = models.Rsync.objects.create(
            rsync_path='/mnt',
            rsync_user='root',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            'id': obj.id,
            'rsync_archive': False,
            'rsync_compress': True,
            'rsync_daymonth': '*',
            'rsync_dayweek': '*',
            'rsync_delete': False,
            'rsync_desc': '',
            'rsync_direction': 'push',
            'rsync_enabled': True,
            'rsync_extra': '',
            'rsync_hour': '*',
            'rsync_minute': '00',
            'rsync_mode': 'module',
            'rsync_month': '*',
            'rsync_path': '/mnt',
            'rsync_preserveattr': False,
            'rsync_preserveperm': False,
            'rsync_quiet': False,
            'rsync_recursive': True,
            'rsync_remotehost': '',
            'rsync_remotemodule': '',
            'rsync_remotepath': '',
            'rsync_remoteport': 22,
            'rsync_times': True,
            'rsync_user': 'root'
        }])

    def test_Update(self):
        obj = models.Rsync.objects.create(
            rsync_path='/mnt/tank',
            rsync_user='root',
            rsync_recursive=True,
            rsync_remotehost='testhost',
            rsync_remotemodule='testmodule',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'rsync_recursive': False,
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['rsync_recursive'], False)

    def test_Delete(self):
        obj = models.Rsync.objects.create(
            rsync_path='/mnt/tank',
            rsync_user='root',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)


class SMARTTestResourceTest(APITestCase):

    def setUp(self):
        super(SMARTTestResourceTest, self).setUp()
        self._disk1 = Disk.objects.create(
            disk_name='ada1',
        )
        self._disk2 = Disk.objects.create(
            disk_name='ada2',
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
                'smarttest_disks': [self._disk1.id, self._disk2.id],
                'smarttest_type': 'L',
                'smarttest_hour': '*',
                'smarttest_daymonth': '*',
                'smarttest_month': '*',
                'smarttest_dayweek': '*',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            'id': 1,
            'smarttest_daymonth': '*',
            'smarttest_dayweek': '*',
            'smarttest_desc': '',
            'smarttest_disks': [1, 2],
            'smarttest_hour': '*',
            'smarttest_month': '*',
            'smarttest_type': 'L'
        })

    def test_Retrieve(self):
        obj = models.SMARTTest.objects.create(
            smarttest_type='L',
        )
        obj.smarttest_disks.add(self._disk1)
        obj.smarttest_disks.add(self._disk2)
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [{
            'id': obj.id,
            'smarttest_daymonth': '*',
            'smarttest_dayweek': '*',
            'smarttest_desc': '',
            'smarttest_disks': [1, 2],
            'smarttest_hour': '*',
            'smarttest_month': '*',
            'smarttest_type': 'L'
        }])

    def test_Update(self):
        obj = models.SMARTTest.objects.create(
            smarttest_type='L',
        )
        obj.smarttest_disks.add(self._disk1)
        obj.smarttest_disks.add(self._disk2)
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'smarttest_type': 'S',
                'smarttest_disks': [self._disk1.id, self._disk2.id],  #FIXME
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['smarttest_type'], 'S')

    def test_Delete(self):
        obj = models.SMARTTest.objects.create(
            smarttest_type='L',
        )
        obj.smarttest_disks.add(self._disk1)
        obj.smarttest_disks.add(self._disk2)
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)
