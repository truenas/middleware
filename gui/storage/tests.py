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

from django.core.urlresolvers import reverse
from django.conf import settings

from storage import models
from freeadmin.tests import TestCase

class UrlsTest(TestCase):

    def setUp(self):
        super(UrlsTest, self).setUp()
        #models.Volume.objects.create(
        #    vol_name="myzpool",
        #    )
        #models.DiskGroup.objects.create(
        #    )

    def test_status(self):
        response = self.client.get(reverse('storage_home'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('storage_tasks'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('storage_volumes'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('storage_replications'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('storage_snapshots'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('storage_dataset'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('storage_wizard'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('storage_import'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('storage_autoimport'))
        self.assertEqual(response.status_code, 200)
