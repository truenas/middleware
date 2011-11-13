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

from sharing import models
from storage.models import MountPoint, Volume
from account.models import bsdUsers, bsdGroups
from freeadmin.tests import TestCase

class UrlsTest(TestCase):

    def setUp(self):
        super(UrlsTest, self).setUp()

    def test_status(self):
        response = self.client.get(reverse('sharing_home'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('sharing_windows'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('sharing_apple'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('sharing_unix'))
        self.assertEqual(response.status_code, 200)

    """
    This test require a known user system
    skipped for now
    def test_share(self):
        vol = Volume.objects.create(
            vol_name="myzpool",
            )
        #models.DiskGroup.objects.create(
        #    )
        mp = MountPoint.objects.create(
            mp_volume=vol,
            mp_path='/mnt/test',
            )

        group = bsdGroups.objects.create(
            bsdgrp_gid=1000,
            bsdgrp_group='www',
            )
        user = bsdUsers.objects.create(
            bsdusr_username='www',
            bsdusr_uid=1000,
            bsdusr_full_name='WWW',
            bsdusr_group=group,
            )

        response = self.client.post(reverse('freeadmin_model_add', kwargs={'app':'sharing', 'model':'CIFS_Share'}), {
            'cifs_name': 'testshare',
            'cifs_comment': 'Test Share',
            'cifs_path': mp.id,
            'cifs_guest': 'www',
            #'': ''.
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')


        json = simplejson.loads(response.content)
        self.assertEqual(json['error'], False)

        models.bsdUsers.objects.get(bsdusr_username='djangotest')
    """
