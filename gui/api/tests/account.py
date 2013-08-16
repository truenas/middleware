from .utils import APITestCase
from freenasUI.account import models


class UserResourceTest(APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get('/api/v1.0/account/bsdusers/', format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            '/api/v1.0/account/bsdusers/',
            format='json',
            data={
                'bsdusr_uid': '1100',
                'bsdusr_username': 'juca',
                'bsdusr_home': '/nonexistent',
                'bsdusr_mode': '755',
                'bsdusr_creategroup': 'on',
                'bsdusr_password1': '12345',
                'bsdusr_password2': '12345',  #FIXME: Only one pwd
                'bsdusr_shell': '/usr/local/bin/bash',
                'bsdusr_full_name': 'Juca Xunda',
                'bsdusr_email': 'juca@xunda.com',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data['bsdusr_uid'], 1100)
        self.assertEqual(data['bsdusr_full_name'], 'Juca Xunda')
        self.assertEqual(data['bsdusr_email'], 'juca@xunda.com')
        self.assertEqual(data['bsdusr_shell'], '/usr/local/bin/bash')
        self.assertEqual(data['bsdusr_builtin'], False)

    def test_Retrieve_sysctl(self):
        obj = models.bsdUsers.objects.create(
            bsdusr_uid=1100,
            bsdusr_group=models.bsdGroups.objects.create(
                bsdgrp_gid=1101,
                bsdgrp_group='juca'
            ),
            bsdusr_username='juca',
            bsdusr_shell='/usr/local/bin/bash',
            bsdusr_full_name='Juca Xunda',
        )
        resp = self.api_client.get(
            '/api/v1.0/account/bsdusers/',
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, [
            {
                u'id': obj.id,
                u'bsdusr_uid': 1100,
                u'bsdusr_username': u'juca',
                u'bsdusr_shell': u'/usr/local/bin/bash',
                u'bsdusr_email': u'',
                u'bsdusr_group': 1101,
                u'bsdusr_home': u'/nonexistent',
                u'bsdusr_full_name': u'Juca Xunda',
                u'bsdusr_builtin': False,
                u'bsdusr_unixhash': u'*',
                u'bsdusr_smbhash': u'*',
                u'bsdusr_password_disabled': False,
                u'bsdusr_locked': False,
            }
        ])

    def test_Update_sysctl(self):
        obj = models.bsdUsers.objects.create(
            bsdusr_uid=1100,
            bsdusr_group=models.bsdGroups.objects.create(
                bsdgrp_gid=1101,
                bsdgrp_group='juca'
            ),
            bsdusr_username='juca',
            bsdusr_shell='/usr/local/bin/bash',
            bsdusr_full_name='Juca Xunda',
        )
        resp = self.api_client.put(
            '/api/v1.0/account/bsdusers/%d/' % obj.id,
            format='json',
            data={
                'bsdusr_full_name': 'Juca Xunda Junior',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)

    def test_Delete_sysctl(self):
        obj = models.bsdUsers.objects.create(
            bsdusr_uid=1100,
            bsdusr_group=models.bsdGroups.objects.create(
                bsdgrp_gid=1101,
                bsdgrp_group='juca'
            ),
            bsdusr_username='juca',
            bsdusr_shell='/usr/local/bin/bash',
            bsdusr_full_name='Juca Xunda',
        )
        resp = self.api_client.delete(
            '/api/v1.0/account/bsdusers/%d/' % obj.id,
            format='json',
        )
        self.assertHttpAccepted(resp)
