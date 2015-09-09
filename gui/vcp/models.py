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

import utils

from django.db import models
from freenasUI.freeadmin.models import Model
from django.utils.translation import ugettext_lazy as _
from freenasUI.contrib.IPAddressField import (IPAddressField, IP4AddressField,IP6AddressField)

class VcenterConfiguration(Model):

    ip_choices = utils.get_management_ips()

    vc_management_ip = models.CharField(
        max_length = 120,
        verbose_name = _("TrueNAS Management IP Address"),
        choices=zip(ip_choices,ip_choices), default='1',
        help_text = 'Please select the TrueNAS interface that vCenter Web client can route to.',
        )

    vc_ip = IP4AddressField(
        blank = False,
        default = '',
        verbose_name = _("vCenter Hostname/IP Address"),
        )

    vc_port = models.CharField(
        max_length = 120,
        default = '443',
        verbose_name = _("vCenter Port"),
        )

    vc_username = models.CharField(
        max_length = 120,
        verbose_name = _("vCenter User name"),
        )

    vc_password = models.CharField(
        blank = True,
        null = True,
        max_length = 120,
        verbose_name = _("vCenter Password"),
        )

    vc_version = models.CharField(
        blank = True,
        null = True,
        max_length=120,
        verbose_name = _("version"),
        )

    class Meta:
        verbose_name = _("VCenter Configuration")
        verbose_name_plural = _("VCenter Configuration")

    class FreeAdmin:
        icon_model = 'VsphereIcon'
        icon_object = 'VsphereIcon'
        icon_view = 'VsphereIcon'
        icon_add = 'VsphereIcon'