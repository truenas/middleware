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

import logging

from dojango import forms
from django.utils.translation import ugettext_lazy as _
from freenasUI.common.forms import ModelForm
from freenasUI.middleware.client import client
from freenasUI.middleware.form import MiddlewareModelForm
from freenasUI.vcp import models
from django.forms import widgets
from freenasUI.system.models import Settings

import freenasUI.vcp.utils as utils
import freenasUI.vcp.plugin as plugin

log = logging.getLogger('vcp.forms')


class VcenterConfigurationForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = 'vc_'
    middleware_attr_schema = 'vcenter_'
    middleware_plugin = 'vcenter'
    is_singletone = True

    vcp_action = None
    vcp_version = ''
    vcp_name = 'TrueNAS vCenter Plugin'
    vcp_is_update_available = False
    vcp_is_installed = False
    vcp_available_version = ''
    is_https = False

    def is_update_needed(self):
        with client as c:
            update = c.call('vcenter.is_update_available')
        if update:
            self.vcp_is_update_available = True

    def middleware_clean(self, data):
        data['action'] = self.vcp_action
        return data

    def get_sys_protocol(self):
        # FIXME:
        try:
            obj = Settings.objects.latest('id')
            sys_guiprotocol = obj.stg_guiprotocol
            if sys_guiprotocol == 'httphttps':
                sys_guiprotocol = 'http'
            return sys_guiprotocol
        except:
            return 'http'

    class Meta:
        model = models.VcenterConfiguration
        exclude = ['vc_version', 'vc_installed']
        widgets = {
            'vc_password': forms.PasswordInput(),
        }

    def __init__(self, *args, **kwargs):
        super(VcenterConfigurationForm, self).__init__(*args, **kwargs)
        sys_guiprotocol = self.get_sys_protocol()
        if sys_guiprotocol.upper() == "HTTPS":
            self.is_https = True
        else:
            self.is_https = False
        ip_choices = utils.get_management_ips()
        self.fields['vc_management_ip'] = forms.ChoiceField(choices=list(zip(
            ip_choices, ip_choices)), label=_('TrueNAS Management IP Address'),)
        obj = models.VcenterConfiguration.objects.latest('id')
        self.vcp_is_installed = obj.vc_installed


class VcenterAuxSettingsForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.VcenterAuxSettings

    def __init__(self, *args, **kwargs):
        super(VcenterAuxSettingsForm, self).__init__(*args, **kwargs)
        self.instance._original_vc_enable_https = self.instance.vc_enable_https
        self.fields["vc_enable_https"].widget.attrs["onChange"] = (
            "vcenter_https_enable_check();"
        )

    def get_sys_url(self, request_address):
        obj = Settings.objects.latest('id')
        proto = obj.stg_guiprotocol
        if proto == 'httphttps':
            proto = 'http'
        if obj.stg_guiaddress == '0.0.0.0':
            address = request_address
        else:
            address = obj.stg_guiaddress
        newurl = '{0}://{1}'.format(proto, address)
        if obj.stg_guiport and proto == 'http':
            newurl += ':{0}'.format(obj.stg_guiport)
        elif obj.stg_guihttpsport and proto == 'https':
            newurl += ':{0}'.format(obj.stg_guihttpsport)
        return newurl

    def done(self, request, events):
        if (self.instance._original_vc_enable_https != self.instance.vc_enable_https):
            events.append(
                "restartHttpd('{0}')".format(
                    self.get_sys_url(request.META['HTTP_HOST'].split(':')[0])
                )
            )
