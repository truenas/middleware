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
from freenasUI.choices import IPChoices
from freenasUI.middleware.client import client
from freenasUI.middleware.form import MiddlewareModelForm
from freenasUI.vcp import models


log = logging.getLogger('vcp.forms')


class VcenterConfigurationForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = 'vc_'
    middleware_attr_schema = 'vcenter'
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
            version = c.call('vcenter.get_plugin_version')
        if update and self.instance.vc_installed:
            self.vcp_is_update_available = True
        else:
            self.vcp_is_update_available = False

        self.vcp_available_version = version
        self.vcp_version = self.instance.vc_version

        return self.vcp_is_update_available

    def middleware_clean(self, data):
        data['action'] = self.vcp_action
        return data

    def get_sys_protocol(self):
        with client as c:
            return c.call('system.general.config')['ui_protocol']

    class Meta:
        model = models.VcenterConfiguration
        exclude = ['vc_version', 'vc_installed']
        widgets = {
            'vc_password': forms.PasswordInput(),
        }

    def __init__(self, *args, **kwargs):
        super(VcenterConfigurationForm, self).__init__(*args, **kwargs)

        self.fields['vc_management_ip'] = forms.ChoiceField(
            choices=list(IPChoices()),
            label=_('TrueNAS Management IP Address')
        )

        self.is_https = True if 'https' in self.get_sys_protocol().lower() else False
        self.vcp_is_installed = self.instance.vc_installed
        self.is_update_needed()


class VcenterAuxSettingsForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = 'vc_'
    middleware_attr_schema = 'vcenter_aux'
    middleware_plugin = 'vcenteraux'
    is_singletone = True

    class Meta:
        fields = '__all__'
        model = models.VcenterAuxSettings

    def __init__(self, *args, **kwargs):
        super(VcenterAuxSettingsForm, self).__init__(*args, **kwargs)
        self.original_https_val = self.instance.vc_enable_https
        self.fields["vc_enable_https"].widget.attrs["onChange"] = (
            "vcenter_https_enable_check();"
        )

    def get_sys_url(self, request_address):
        with client as c:
            sys_config = c.call('system.general.config')

        proto = sys_config['ui_protocol'] if sys_config['ui_protocol'].lower() != 'httphttps' else 'http'
        address = request_address if sys_config['ui_address'] == '0.0.0.0' else sys_config['ui_address']
        newurl = f'{proto}://{address}'

        if sys_config['ui_port'] and proto == 'http':
            newurl += f':{sys_config["ui_port"]}'
        elif sys_config['ui_httpsport'] and proto == 'https':
            newurl += f':{sys_config["ui_httpsport"]}'
        return newurl

    def done(self, request, events):
        if self.original_https_val != self.instance.vc_enable_https:
            events.append(
                "restartHttpd('{0}')".format(
                    self.get_sys_url(request.META['HTTP_HOST'].split(':')[0])
                )
            )
