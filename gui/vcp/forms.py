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
    is_https = False

    def clean_vc_management_ip(self):
        manage_ip = str(self.cleaned_data['vc_management_ip'])
        if '--Select--' in manage_ip:
            raise forms.ValidationError(
                _('Please select the TrueNAS management interface.')
            )
        return manage_ip

    def install_plugin(self):
        try:
            if self.is_in_db() is True:
                self.vcp_status = 'Plugin is already installed.'
                return False
            ip = str(self.cleaned_data['vc_ip'])
            port = str(self.cleaned_data['vc_port'])
            manage_ip = str(self.cleaned_data['vc_management_ip'])
            password = str(self.cleaned_data['vc_password'])
            username = str(self.cleaned_data['vc_username'])
            sys_guiprotocol = self.get_sys_protocol()
            if self.get_aux_enable_https() == False and sys_guiprotocol.upper() == 'HTTPS':
                self.vcp_status = 'Please enable vCenter Plugin over https.'
                return False

            status_flag = self.validate_vcp_param(
                ip, port, username, password, False)
            if status_flag is True:
                thumb_print = self.get_thumb_print(manage_ip, sys_guiprotocol)
                if thumb_print is None:
                    return False

                status_flag = utils.update_plugin_zipfile(
                    ip, username, password, port, 'NEW', 'null', utils.get_plugin_version())
                if status_flag is True:
                    vcp_url = self.get_vcp_url(manage_ip, sys_guiprotocol)
                    plug = plugin.PluginManager()
                    status_flag = plug.install_vCenter_plugin(
                        ip, username, password, port, vcp_url, thumb_print)
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
            if self.is_in_db() is False:
                self.vcp_status = 'Plugin is not installed.'
                return False
            obj = models.VcenterConfiguration.objects.latest('id')
            ip = str(obj.vc_ip)
            username = str(self.cleaned_data['vc_username'])
            password = str(self.cleaned_data['vc_password'])
            port = str(self.cleaned_data['vc_port'])

            status_flag = self.validate_vcp_param(
                ip, port, username, password, True)
            if status_flag is True:
                plug = plugin.PluginManager()
                status_flag = plug.uninstall_vCenter_plugin(
                    ip, username, password, port)
                if status_flag is True:
                    models.VcenterConfiguration.objects.all().delete()
                    self.vcp_is_installed = False
                    return True
                elif 'permission' in status_flag:
                    self.vcp_status = status_flag
                    return False
                else:
                    self.vcp_status = 'Uninstall failed. Please contact support.'
                    return False
            elif 'does not exist' in status_flag:
                models.VcenterConfiguration.objects.all().delete()
                self.vcp_is_installed = False
                return True
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
            version_old = str(obj.vc_version)
            username = str(self.cleaned_data['vc_username'])
            password = str(self.cleaned_data['vc_password'])
            port = str(self.cleaned_data['vc_port'])
            manage_ip = str(self.cleaned_data['vc_management_ip'])

            sys_guiprotocol = self.get_sys_protocol()
            if self.get_aux_enable_https() == False and sys_guiprotocol.upper() == 'HTTPS':
                self.vcp_status = 'Please enable vCenter Plugin over https.'
                return False

            status_flag = self.validate_vcp_param(
                ip, port, username, password, True)

            if status_flag is True:
                thumb_print = self.get_thumb_print(manage_ip, sys_guiprotocol)
                if thumb_print is None:
                    return False

                status_flag = utils.update_plugin_zipfile(
                    ip, username, password, port, 'UPGRADE', version_old, utils.get_plugin_version())
                if status_flag is True:
                    vcp_url = self.get_vcp_url(manage_ip, sys_guiprotocol)
                    plug = plugin.PluginManager()
                    status_flag = plug.upgrade_vCenter_plugin(
                        ip, username, password, port, vcp_url, thumb_print)
                    if status_flag is True:
                        self.vcp_is_update_available = False
                        obj.vc_version = utils.get_plugin_version()
                        obj.vc_username = username
                        obj.vc_port = port
                        obj.vc_management_ip = manage_ip
                        obj.save()
                        return True
                    elif 'permission' in status_flag:
                        self.vcp_status = status_flag
                        return False
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
            if self.is_in_db() is False:
                self.vcp_status = 'Plugin is not installed.'
                return False
            obj = models.VcenterConfiguration.objects.latest('id')
            ip = str(obj.vc_ip)
            username = str(self.cleaned_data['vc_username'])
            password = str(self.cleaned_data['vc_password'])
            port = str(self.cleaned_data['vc_port'])
            manage_ip = str(self.cleaned_data['vc_management_ip'])

            sys_guiprotocol = self.get_sys_protocol()
            if self.get_aux_enable_https() == False and sys_guiprotocol.upper() == 'HTTPS':
                self.vcp_status = 'Please first enable vCenter Plugin over https.'
                return False

            status_flag = self.validate_vcp_param(
                ip, port, username, password, False)
            if status_flag is True:
                thumb_print = self.get_thumb_print(manage_ip, sys_guiprotocol)
                if thumb_print is None:
                    return False

                status_flag = utils.update_plugin_zipfile(
                    ip, username, password, port, 'REPAIR', 'null', utils.get_plugin_version())
                if status_flag is True:
                    vcp_url = self.get_vcp_url(manage_ip, sys_guiprotocol)
                    plug = plugin.PluginManager()
                    status_flag = plug.install_vCenter_plugin(
                        ip, username, password, port, vcp_url, thumb_print)
                    if status_flag is True:
                        obj.vc_username = username
                        obj.vc_port = port
                        obj.vc_management_ip = manage_ip
                        obj.save()
                        return True
                    elif 'permission' in status_flag:
                        self.vcp_status = 'vCenter user has no permission to repair the plugin.'
                        return False
                    else:
                        self.vcp_status = 'Repair failed. Please contact support.'
                        return False
                else:
                    self.vcp_status = 'Repair failed. Please contact support.'
                    return False
            elif 'already' in status_flag:
                self.vcp_status = 'Plugin repair is not required.'
                return False
            else:
                self.vcp_status = status_flag
                return False
        except Exception:
            self.vcp_status = 'Repair failed. Please contact support.'
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

    def get_sys_port(self):
        try:
            sys_guiport = '80'
            obj = Settings.objects.latest('id')
            sys_guiprotocol = obj.stg_guiprotocol
            if sys_guiprotocol == 'https':
                sys_guiport = obj.stg_guihttpsport
            else:
                sys_guiport = obj.stg_guiport
            return str(sys_guiport)
        except:
            return '80'

    def get_vcp_url(self, manage_ip, sys_guiprotocol):
        sys_guiport = self.get_sys_port()
        file_address = 'static/' + utils.get_plugin_file_name()
        vcp_url = sys_guiprotocol + '://' + manage_ip + \
            ':' + sys_guiport + '/' + file_address
        return vcp_url

    def is_in_db(self):
        try:
            obj = models.VcenterConfiguration.objects.latest('id')
            ip = str(obj.vc_ip)
            if ip != '':
                return True
            else:
                return False
        except Exception:
            return False

    def get_thumb_print(self, manage_ip, sys_guiprotocol):
        thumb_print = ''
        if sys_guiprotocol.upper() == "HTTPS":
            port = self.get_sys_port()
            thumb_print = utils.get_thumb_print(manage_ip, port)
            if thumb_print is None:
                self.vcp_status = 'Could not retrieve SHA1 fingure print. Please try after some time.'
        return thumb_print

    def get_aux_enable_https(self):
        aux_enable_https = False
        try:
            aux_enable_https = models.VcenterAuxSettings.objects.latest(
                'id').vc_enable_https
            return aux_enable_https
        except Exception:
            return False

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
                elif 'FindExtension' in status_flag:
                    return 'Please provide a valid vCenter server IP address.'
                elif 'no permission' in status_flag:
                    return status_flag
                else:
                    return 'Operation failed. Please contact support.'
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
