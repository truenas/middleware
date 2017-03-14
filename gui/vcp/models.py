#
# Copyright 2015 iXsystems, Inc.
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
from . import utils

from django.db import models
from freenasUI.freeadmin.models import Model
from django.utils.translation import ugettext_lazy as _
from freenasUI.contrib.IPAddressField import IP4AddressField
from django.core.validators import RegexValidator


class VcenterConfiguration(Model):

    port_regex = RegexValidator(
        regex=r'^\+?1?\d{1,5}$',
        message="Please Enter a whole number.")

    vc_management_ip = models.CharField(
        max_length=120,
        verbose_name=_(" TrueNAS Management IP Address"),
        default='1',
        help_text=_(
            'Please select the TrueNAS interface that vCenter Web client can '
            'route to.'
        ),
    )
    vc_ip = models.CharField(
        blank=False,
        default='',
        max_length=120,
        verbose_name=_(" vCenter Hostname/IP Address"),
    )
    vc_port = models.CharField(
        max_length=5,
        default='443',
        validators=[port_regex],
        verbose_name=_(" vCenter Port"),
    )
    vc_username = models.CharField(
        max_length=120,
        verbose_name=_(" vCenter Username"),
    )
    vc_password = models.CharField(
        max_length=120,
        verbose_name=_(" vCenter Password"),
    )
    vc_version = models.CharField(
        blank=True,
        null=True,
        max_length=120,
        verbose_name=_(" version"),
    )

    class Meta:
        verbose_name = _("vCenter Configuration")
        verbose_name_plural = _("vCenter Configurations")

    class FreeAdmin:
        icon_model = 'VsphereIcon'
        icon_object = 'VsphereIcon'
        icon_view = 'VsphereIcon'
        icon_add = 'VsphereIcon'


class VcenterAuxSettings(Model):

    vc_enable_https = models.BooleanField(
        default=False,
        verbose_name=_(" Enable vCenter Plugin over https"),
    )

    class Meta:
        verbose_name = _("vCenter Auxiliary Settings")
        verbose_name_plural = _("vCenter Auxiliary Settings")

    class FreeAdmin:
        deletable = False
        icon_model = "SettingsIcon"
