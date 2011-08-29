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
# $FreeBSD$
#####################################################################

from django.core.urlresolvers import reverse
from django.conf import settings

from services import models
from freeadmin.tests import TestCase

class UrlsTest(TestCase):

    def setUp(self):
        super(UrlsTest, self).setUp()
        models.services.objects.create(srv_service='ldap',srv_enable=False)
        models.services.objects.create(srv_service='activedirectory',srv_enable=False)
        models.CIFS.objects.create()
        models.FTP.objects.create()
        models.TFTP.objects.create()
        models.NFS.objects.create()
        models.DynamicDNS.objects.create()
        models.AFP.objects.create()
        models.SNMP.objects.create()
        models.SSH.objects.create()
        models.ActiveDirectory.objects.create()
        models.LDAP.objects.create()
        models.iSCSITargetGlobalConfiguration.objects.create()

    def test_status(self):
        response = self.client.get(reverse('services_home'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('freeadmin_model_edit', kwargs={'app':'services','model': 'CIFS', 'oid': models.CIFS.objects.all().order_by('-id')[0].id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('freeadmin_model_edit', kwargs={'app':'services','model': 'FTP', 'oid': models.FTP.objects.all().order_by('-id')[0].id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('freeadmin_model_edit', kwargs={'app':'services','model': 'TFTP', 'oid': models.TFTP.objects.all().order_by('-id')[0].id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('freeadmin_model_edit', kwargs={'app':'services','model': 'NFS', 'oid': models.NFS.objects.all().order_by('-id')[0].id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('freeadmin_model_edit', kwargs={'app':'services','model': 'DynamicDNS', 'oid': models.DynamicDNS.objects.all().order_by('-id')[0].id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('freeadmin_model_edit', kwargs={'app':'services','model': 'AFP', 'oid': models.AFP.objects.all().order_by('-id')[0].id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('freeadmin_model_edit', kwargs={'app':'services','model': 'SNMP', 'oid': models.SNMP.objects.all().order_by('-id')[0].id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('freeadmin_model_edit', kwargs={'app':'services','model': 'SSH', 'oid': models.SSH.objects.all().order_by('-id')[0].id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('freeadmin_model_edit', kwargs={'app':'services','model': 'LDAP', 'oid': models.LDAP.objects.all().order_by('-id')[0].id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('freeadmin_model_edit', kwargs={'app':'services','model': 'ActiveDirectory', 'oid': models.ActiveDirectory.objects.all().order_by('-id')[0].id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('freeadmin_model_edit', kwargs={'app':'services','model': 'iSCSITargetGlobalConfiguration', 'oid': models.iSCSITargetGlobalConfiguration.objects.all().order_by('-id')[0].id}))
        self.assertEqual(response.status_code, 200)
