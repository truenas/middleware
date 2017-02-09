# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.api.tests.utils import APITestCase
from freenasUI.account import models


class UsersResourceTest(APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'bsdusr_uid': '1100',
                'bsdusr_username': 'juca',
                'bsdusr_home': '/nonexistent',
                'bsdusr_mode': '755',
                'bsdusr_creategroup': 'on',
                'bsdusr_password': '12345',
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

    def test_Retrieve(self):
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
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertTrue({
            'id': obj.id,
            'bsdusr_uid': 1100,
            'bsdusr_username': 'juca',
            'bsdusr_shell': '/usr/local/bin/bash',
            'bsdusr_email': '',
            'bsdusr_group': 1101,
            'bsdusr_home': '/nonexistent',
            'bsdusr_full_name': 'Juca Xunda',
            'bsdusr_builtin': False,
            'bsdusr_unixhash': '*',
            'bsdusr_smbhash': '*',
            'bsdusr_password_disabled': False,
            'bsdusr_locked': False,
            'bsdusr_sudo': False,
            'bsdusr_sshpubkey': '',
        } in data)

    def test_Update(self):
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
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'bsdusr_full_name': 'Juca Xunda Junior',
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)

    def test_Delete(self):
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
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)

    def test_Password(self):
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
        resp = self.api_client.post(
            '%s%d/password/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'bsdusr_password': 'testpw',
            }
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)

    def test_Groups_retrieve(self):
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
        group = models.bsdGroups.objects.create(
            bsdgrp_gid=100,
            bsdgrp_group='mail',
        )
        models.bsdGroupMembership.objects.create(
            bsdgrpmember_group=group,
            bsdgrpmember_user=obj,
        )
        resp = self.api_client.get(
            '%s%d/groups/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, ["mail"])

    def test_Groups_update(self):
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
        models.bsdGroups.objects.create(
            bsdgrp_gid=100,
            bsdgrp_group='mail',
        )
        resp = self.api_client.post(
            '%s%d/groups/' % (self.get_api_url(), obj.id),
            format='json',
            data=['mail'],
        )
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        self.assertEqual(data, ["mail"])


class GroupsResourceTest(APITestCase):

    def test_get_list_unauthorzied(self):
        self.assertHttpUnauthorized(
            self.client.get(self.get_api_url(), format='json')
        )

    def test_Create(self):
        resp = self.api_client.post(
            self.get_api_url(),
            format='json',
            data={
                'bsdgrp_gid': 1100,
                'bsdgrp_group': 'testgroup',
            }
        )
        self.assertHttpCreated(resp)
        self.assertValidJSON(resp.content)

        data = self.deserialize(resp)
        self.assertEqual(data, {
            'id': 2,
            'bsdgrp_builtin': False,
            'bsdgrp_gid': 1100,
            'bsdgrp_group': 'testgroup',
            'bsdgrp_sudo': False,
        })

    def test_Retrieve(self):
        obj = models.bsdGroups.objects.create(
            bsdgrp_gid=1100,
            bsdgrp_group='testgroup',
        )
        resp = self.api_client.get(
            self.get_api_url(),
            format='json',
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertTrue({
            'id': obj.id,
            'bsdgrp_builtin': False,
            'bsdgrp_gid': 1100,
            'bsdgrp_group': 'testgroup',
            'bsdgrp_sudo': False,
        } in data)

    def test_Update(self):
        obj = models.bsdGroups.objects.create(
            bsdgrp_gid=1100,
            bsdgrp_group='testgroup',
        )
        resp = self.api_client.put(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
            data={
                'bsdgrp_group': 'testgroup2',
            }
        )
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertEqual(data['id'], obj.id)
        self.assertEqual(data['bsdgrp_group'], 'testgroup2')

    def test_Delete(self):
        obj = models.bsdGroups.objects.create(
            bsdgrp_gid=1100,
            bsdgrp_group='testgroup',
        )
        resp = self.api_client.delete(
            '%s%d/' % (self.get_api_url(), obj.id),
            format='json',
        )
        self.assertHttpAccepted(resp)
