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
from freenasUI.vcp import models
from django.forms import widgets
from freenasUI.system.models import Settings

from . import plugin, utils

log = logging.getLogger('vcp.forms')


class VcenterConfigurationForm(ModelForm):

    vcp_version = ''
    vcp_name = 'TrueNAS vCenter Plugin'
    vcp_is_update_available = False
    vcp_is_installed = False
    vcp_status = ''
    vcp_available_version = ''

    def clean_vc_management_ip(self):
        manage_ip = str(self.cleaned_data['vc_management_ip'])
        if '--Select--' in manage_ip:
            raise forms.ValidationError(
                _('Please select the TrueNAS management interface.')
            )
        return manage_ip

    def install_plugin(self):
        try:
            ip = str(self.cleaned_data['vc_ip'])
            port = str(self.cleaned_data['vc_port'])
            manage_ip = str(self.cleaned_data['vc_management_ip'])
            password = str(self.cleaned_data['vc_password'])
            username = str(self.cleaned_data['vc_username'])
            status_flag = self.validate_vcp_param(
                ip, port, username, password, False)

            if status_flag is True:
                status_flag = utils.update_plugin_zipfile(
                    ip, username, password, port, 'NEW', utils.get_plugin_version())
                if status_flag is True:
                    sys_guiprotocol = self.get_sys_protocol()
                    plug = plugin.PluginManager()
                    status_flag = plug.install_vCenter_plugin(
                        ip, username, password, port, manage_ip, sys_guiprotocol)
                    if status_flag is True:
                        self.vcp_is_installed = True
                        self.vcp_is_update_available = False
                        # Just for cleaning purpose
                        models.VcenterConfiguration.objects.all().delete()
                        return True
                    elif 'permission' in status_flag:
                        self.vcp_status = status_flag
                        return False
                    else:
                        self.vcp_status = 'Installation failed. Please contact support.'
                        return False
                else:
                    self.vcp_status = 'Installation failed. Please contact support.'
                    return False
            else:
                self.vcp_status = status_flag
                return False

        except Exception:
            self.vcp_status = 'Installation failed. Please contact support.'
            return False

    def uninstall_plugin(self):
        try:
            obj = models.VcenterConfiguration.objects.latest('id')
            ip = str(obj.vc_ip)
            username = str(obj.vc_username)
            password = str(self.cleaned_data['vc_password'])
            port = str(obj.vc_port)
            status_flag = self.validate_vcp_param(
                ip, port, username, password, True
            )

            if status_flag is True:
                plug = plugin.PluginManager()
                status_flag = plug.uninstall_vCenter_plugin(
                    ip, username, password, port)
                if status_flag is True:
                    models.VcenterConfiguration.objects.all().delete()
                    self.vcp_is_installed = False
                    return True
                else:
                    self.vcp_status = 'Uninstall failed. Please contact support.'
                    return False
            else:
                self.vcp_status = status_flag
                return False

        except Exception:
            self.vcp_status = 'Uninstall failed. Please contact support.'
            return False

    def upgrade_plugin(self):
        try:
            obj = models.VcenterConfiguration.objects.latest('id')
            ip = str(obj.vc_ip)
            username = str(obj.vc_username)
            password = str(self.cleaned_data['vc_password'])
            port = str(obj.vc_port)
            manage_ip = str(obj.vc_management_ip)
            status_flag = self.validate_vcp_param(
                ip, port, username, password, True)

            if status_flag is True:
                status_flag = utils.update_plugin_zipfile(
                    ip, username, password, port, 'UPGRADE', utils.get_plugin_version())
                if status_flag is True:
                    sys_guiprotocol = self.get_sys_protocol()
                    plug = plugin.PluginManager()
                    status_flag = plug.upgrade_vCenter_plugin(
                        ip, username, password, port, manage_ip, sys_guiprotocol)
                    if status_flag is True:
                        self.vcp_is_update_available = False
                        obj.vc_version = utils.get_plugin_version()
                        obj.save()
                        return True
                    else:
                        self.vcp_status = 'Upgrade failed. Please contact support.'
                        return False
                else:
                    self.vcp_status = 'Upgrade failed. Please contact support.'
                    return False
            else:
                self.vcp_status = status_flag
                return False
        except Exception:
            self.vcp_status = 'Upgrade failed. Please contact support.'
            return False

    def repair_plugin(self):
        try:
            obj = models.VcenterConfiguration.objects.latest('id')
            ip = str(obj.vc_ip)
            username = str(obj.vc_username)
            password = str(self.cleaned_data['vc_password'])
            port = str(obj.vc_port)
            manage_ip = str(obj.vc_management_ip)
            status_flag = self.validate_vcp_param(
                ip, port, username, password, False)

            if status_flag is True:
                status_flag = utils.update_plugin_zipfile(
                    ip, username, password, port, 'NEW', utils.get_plugin_version())
                if status_flag is True:
                    sys_guiprotocol = self.get_sys_protocol()
                    plug = plugin.PluginManager()
                    status_flag = plug.install_vCenter_plugin(
                        ip, username, password, port, manage_ip, sys_guiprotocol)
                    if status_flag is True:
                        return True
                    else:
                        self.vcp_status = 'repair failed. Please contact support.'
                        return False
                else:
                    self.vcp_status = 'repair failed. Please contact support.'
                    return False
            elif 'already' in status_flag:
                self.vcp_status = 'Plugin repaire is not required.'
                return False
            else:
                self.vcp_status = status_flag
                return False
        except Exception:
            self.vcp_status = 'repair failed. Please contact support.'
            return False

    def is_update_needed(self):
        version_new = utils.get_plugin_version()
        self.vcp_available_version = version_new
        try:
            obj = models.VcenterConfiguration.objects.latest('id')
            version_old = obj.vc_version
            self.vcp_version = obj.vc_version
            self.vcp_is_installed = True
            if self.compare_version(version_new, version_old):
                self.vcp_is_update_available = True
                self.vcp_available_version = version_new
            else:
                self.vcp_is_update_available = False
        except Exception:
            self.vcp_is_update_available = False
            return False

    def compare_version(self, versionNew, versionOld):
        try:
            snew = versionNew.replace(".", "")
            sold = versionOld.replace(".", "")
            if int(snew) > int(sold):
                return True
            else:
                return False
        except:
            return False

    def get_sys_protocol(self):
        try:
            obj = Settings.objects.latest('id')
            sys_guiprotocol = obj.stg_guiprotocol
            if sys_guiprotocol == 'httphttps':
                sys_guiprotocol = 'http'
            return sys_guiprotocol
        except:
            return 'http'

    def validate_vcp_param(self, ip, port, username, password, is_installed):
        try:
            plug = plugin.PluginManager()
            status_flag = plug.check_credential(ip, username, password, port)
            if status_flag is True:
                status_flag = plug.find_plugin(ip, username, password, port)
                if status_flag is False:
                    if is_installed:
                        return 'Plugin does not exist on vCenter server.'
                    else:
                        return True
                elif 'TruNAS System :' in status_flag:
                    if is_installed:
                        return True
                    else:
                        return 'vCenter plugin is already installed from another %s' % status_flag
            else:
                return status_flag
        except Exception:
            return 'Operation failed. Please contact support.'

    class Meta:
        model = models.VcenterConfiguration
        exclude = ['vc_version']
        widgets = {
            'vc_password': forms.PasswordInput(),
        }
