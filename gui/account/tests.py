#+
# Copyright 2010 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

from django.core.urlresolvers import reverse
from django.conf import settings
from django.utils import simplejson

from freenasUI.account import models, forms
from freeadmin.tests import TestCase

class UrlsTest(TestCase):

    def setUp(self):
        super(UrlsTest, self).setUp()
        #models.SSL.objects.create()

    def test_urls(self):
        response = self.client.get(reverse('account_home'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('account_bsduser'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('account_bsduser_json'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('account_bsdgroup'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('account_bsdgroup_json'))
        self.assertEqual(response.status_code, 200)

    def test_logout(self):
        response = self.client.get(settings.LOGOUT_URL)
        self.assertContains(response, "You are now logged out", status_code=200)

        response = self.client.get('/') # test logged in status
        self.assertRedirects(response, settings.LOGIN_URL+'?next=/',
            status_code=302, target_status_code=200)

    def test_createuser(self):
        response = self.client.post(reverse('freeadmin_model_add', kwargs={'app':'account', 'model':'bsdUsers', 'mf': 'bsdUsersForm'}), {
            'bsdusr_uid': '2000',
            'bsdusr_username': 'djangotest',
            'bsdusr_password1': 'mytest',
            'bsdusr_password2': 'mytest',
            'bsdusr_builtin': 'mytest',
            'bsdusr_shell': '/bin/csh',
            'bsdusr_home': '/nonexistent',
            'bsdusr_full_name': 'Django Test',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        json = simplejson.loads(response.content)
        self.assertEqual(json['error'], False)

        models.bsdUsers.objects.get(bsdusr_username='djangotest')
