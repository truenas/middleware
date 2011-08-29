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

from network import models
from freeadmin.tests import TestCase

class UrlsTest(TestCase):

    def setUp(self):
        super(UrlsTest, self).setUp()

    def test_status(self):
        response = self.client.get(reverse('network_home'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('network_lagg'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('network_summary'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('network_interface'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('network_vlan'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('network_staticroute'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('network_lagg_add'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('network_globalconf'))
        self.assertEqual(response.status_code, 200)
