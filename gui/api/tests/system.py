from .utils import APITestCase
from freenasUI.storage.models import MountPoint, Volume
from freenasUI.system import models


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
            u'id': 1,
            u'cron_command': u'ls /',
            u'cron_daymonth': u'*',
            u'cron_dayweek': u'*',
            u'cron_description': u'',
            u'cron_enabled': True,
            u'cron_hour': u'*',
            u'cron_minute': u'*/20',
            u'cron_month': u'*',
            u'cron_stderr': False,
            u'cron_stdout': True,
            u'cron_user': u'root',
        })

    def test_Retrieve(self):
        sysctl = models.CronJob.objects.create(
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
            u'id': sysctl.id,
            u'cron_command': u'ls /',
            u'cron_daymonth': u'*',
            u'cron_dayweek': u'*',
            u'cron_description': u'',
            u'cron_enabled': True,
            u'cron_hour': u'*',
            u'cron_minute': u'00',
            u'cron_month': u'*',
            u'cron_stderr': False,
            u'cron_stdout': True,
            u'cron_user': u'root',
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
        self.assertHttpAccepted(resp)
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
            u'id': 1,
            u'rsync_archive': False,
            u'rsync_compress': True,
            u'rsync_daymonth': u'*',
            u'rsync_dayweek': u'*',
            u'rsync_delete': False,
            u'rsync_desc': u'',
            u'rsync_direction': u'push',
            u'rsync_enabled': True,
            u'rsync_extra': u'',
            u'rsync_hour': u'*',
            u'rsync_minute': u'*/20',
            u'rsync_mode': u'module',
            u'rsync_month': u'*',
            u'rsync_path': u'/mnt/tank',
            u'rsync_preserveattr': False,
            u'rsync_preserveperm': False,
            u'rsync_quiet': False,
            u'rsync_recursive': True,
            u'rsync_remotehost': u'testhost',
            u'rsync_remotemodule': u'testmodule',
            u'rsync_remotepath': u'',
            u'rsync_remoteport': 22,
            u'rsync_times': True,
            u'rsync_user': u'root'
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
            u'id': obj.id,
            u'rsync_archive': False,
            u'rsync_compress': True,
            u'rsync_daymonth': u'*',
            u'rsync_dayweek': u'*',
            u'rsync_delete': False,
            u'rsync_desc': u'',
            u'rsync_direction': u'push',
            u'rsync_enabled': True,
            u'rsync_extra': u'',
            u'rsync_hour': u'*',
            u'rsync_minute': u'00',
            u'rsync_mode': u'module',
            u'rsync_month': u'*',
            u'rsync_path': u'/mnt',
            u'rsync_preserveattr': False,
            u'rsync_preserveperm': False,
            u'rsync_quiet': False,
            u'rsync_recursive': True,
            u'rsync_remotehost': u'',
            u'rsync_remotemodule': u'',
            u'rsync_remotepath': u'',
            u'rsync_remoteport': 22,
            u'rsync_times': True,
            u'rsync_user': u'root'
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
        self.assertHttpAccepted(resp)
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


class SysctlResourceTest(APITestCase):

    def setUp(self):
        super(SysctlResourceTest, self).setUp()

    def tearDown(self):
        super(SysctlResourceTest, self).tearDown()

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create_sysctl(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'sysctl_mib': 'kern.coredump',
                'sysctl_enabled': True,
                'sysctl_value': '1',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            u'id': 1,
            u'sysctl_comment': u'',
            u'sysctl_enabled': True,
            u'sysctl_mib': u'kern.coredump',
            u'sysctl_value': u'1',
        })

    def test_Retrieve_sysctl(self):
        sysctl = models.Sysctl.objects.create(
            sysctl_mib='kern.coredump',
            sysctl_value='2',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [
            {
                u'id': sysctl.id,
                u'sysctl_comment': sysctl.sysctl_comment,
                u'sysctl_enabled': sysctl.sysctl_enabled,
                u'sysctl_mib': sysctl.sysctl_mib,
                u'sysctl_value': sysctl.sysctl_value,
            }
        ])

    def test_Update_sysctl(self):
        sysctl = models.Sysctl.objects.create(
            sysctl_mib='kern.coredump',
            sysctl_value='1',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), sysctl.id),
            format='json',
            data={
                'sysctl_value': '2',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], sysctl.id)
        self.assertEqual(data['sysctl_value'], '2')

    def test_Delete_sysctl(self):
        sysctl = models.Sysctl.objects.create(
            sysctl_mib='kern.coredump',
            sysctl_value='1',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), sysctl.id),
            format='json',
        )
        self.assertHttpAccepted(resp)
