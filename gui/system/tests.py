#+
# Copyright 2010 iXsystems
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
# $FreeBSD$
#####################################################################

from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.conf import settings

from system import models

class UrlsTest(TestCase):

    def setUp(self):
        try:
            user = User.objects.get(username='admin')
        except:
            user = User.objects.create_user('admin', 'freenas@local.domain', 'freenas')
        self.client = Client()
        login = self.client.login(username='admin', password='freenas')

        self.assertEqual(login, True)

        models.Settings.objects.create()
        models.Email.objects.create()
        models.Advanced.objects.create()
        models.SSL.objects.create()

    def test_reporting(self):
        response = self.client.get(reverse('system_reporting'))
        self.assertEqual(response.status_code, 200)

    def test_settings(self):
        response = self.client.get(reverse('system_settings'))
        self.assertEqual(response.status_code, 200)

    def test_advanced(self):
        response = self.client.get(reverse('system_advanced'))
        self.assertEqual(response.status_code, 200)

    def test_info(self):
        response = self.client.get(reverse('system_info'))
        self.assertEqual(response.status_code, 200)

    def test_config(self):
        response = self.client.get(reverse('system_config'))
        self.assertEqual(response.status_code, 200)

    def test_configsave(self):
        response = self.client.get(reverse('system_configsave'))
        self.assertEqual(response.status_code, 200)

    def test_varlog(self):
        response = self.client.get(reverse('system_messages', kwargs={'lines': 200}))
        self.assertEqual(response.status_code, 200)

    def test_top(self):
        response = self.client.get(reverse('system_top'))
        self.assertEqual(response.status_code, 200)

    def test_testmail(self):
        response = self.client.get(reverse('system_testmail'))
        self.assertEqual(response.status_code, 200)

    def test_clearcache(self):
        response = self.client.get(reverse('system_clearcache'))
        self.assertEqual(response.status_code, 200)

    def test_clearcache(self):
        response = self.client.get(reverse('system_clearcache'))
        self.assertEqual(response.status_code, 200)

    def test_firmware(self):
        response = self.client.get(reverse('system_firmwizard'))
        self.assertEqual(response.status_code, 200)
