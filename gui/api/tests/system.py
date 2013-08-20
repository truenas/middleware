from .utils import APITestCase
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
