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

import requests
import ssl
import datetime
import utils

from django.conf import settings
from pyVmomi import vim
from ConfigParser import SafeConfigParser
from pyVim.connect import SmartConnect


class PluginManager:

    property_file_path = settings.HERE + '/vcp/Extensionconfig.ini.dist'

    def get_extensionKey(self):
        cp = SafeConfigParser()
        cp.read(self.property_file_path)
        key = cp.get('RegisterParam', 'key')
        return key

    def get_extension(self, manage_ip, sys_guiprotocol):
        cp = SafeConfigParser()
        cp.read(self.property_file_path)
        company = cp.get('RegisterParam', 'company')
        descr = cp.get('RegisterParam', 'description')
        key = cp.get('RegisterParam', 'key')
        version = utils.get_plugin_version()
        if 'Not available' in version:
            return version
        label = cp.get('RegisterParam', 'label')
        file_address = 'static/' + utils.get_plugin_file_name()
        final_url = sys_guiprotocol + "://" + manage_ip + "/" + file_address
        description = vim.Description()
        description.label = label
        description.summary = descr
        ext = vim.Extension()
        ext.company = company
        ext.version = version
        ext.key = key
        ext.description = description
        ext.lastHeartbeatTime = datetime.datetime.now()

        server_info = [1]
        server_info[0] = vim.Extension.ServerInfo()
        server_info[0].serverThumbprint = ''
        server_info[0].type = sys_guiprotocol.upper()
        server_info[0].url = final_url
        server_info[0].description = description
        server_info[0].company = company
        admin_emails = [1]
        admin_emails[0] = 'none'
        server_info[0].adminEmail = admin_emails
        ext.server = server_info

        client = [1]
        client[0] = vim.Extension.ClientInfo()
        client[0].url = final_url
        client[0].company = company
        client[0].version = version
        client[0].description = description
        client[0].type = "vsphere-client-serenity"

        ext.client = client
        return ext

    def install_vCenter_plugin(
            self,
            vc_ip,
            usernName,
            password,
            port,
            manage_ip,
            sys_guiprotocol):
        try:

            try:
                ssl._create_default_https_context = ssl._create_unverified_context
            except AttributeError:
                print 'Error ssl'
            si = SmartConnect("https", vc_ip, int(port), usernName, password)
            ext = self.get_extension(manage_ip, sys_guiprotocol)
            si.RetrieveServiceContent().extensionManager.RegisterExtension(ext)
            return True

        except vim.fault.NoPermission as ex:
            return 'vCenter user has no permission to install the plugin.'

        except Exception as ex:
            return str(ex).replace("'", "").replace("<", "").replace(">", "")

    def uninstall_vCenter_plugin(self, vc_ip, usernName, password, port):
        try:
            try:
                ssl._create_default_https_context = ssl._create_unverified_context
            except AttributeError:
                print 'Error ssl'
            si = SmartConnect("https", vc_ip, int(port), usernName, password)
            extkey = self.get_extensionKey()
            si.RetrieveServiceContent().extensionManager.UnregisterExtension(extkey)
            return True

        except Exception as ex:
            return str(ex).replace("'", "").replace("<", "").replace(">", "")

    def upgrade_vCenter_plugin(
            self,
            vc_ip,
            usernName,
            password,
            port,
            manage_ip,
            sys_guiprotocol):
        try:

            try:
                ssl._create_default_https_context = ssl._create_unverified_context
            except AttributeError:
                print 'Error ssl'
            si = SmartConnect("https", vc_ip, int(port), usernName, password)
            ext = self.get_extension(manage_ip, sys_guiprotocol)
            si.RetrieveServiceContent().extensionManager.UpdateExtension(ext)
            return True

        except Exception as ex:
            return str(ex).replace("'", "").replace("<", "").replace(">", "")

    def find_plugin(self, vc_ip, usernName, password, port):
        try:

            try:
                ssl._create_default_https_context = ssl._create_unverified_context
            except AttributeError:
                print 'Error ssl'
            si = SmartConnect("https", vc_ip, int(port), usernName, password)
            extkey = self.get_extensionKey()
            ext = si.RetrieveServiceContent().extensionManager.FindExtension(extkey)
            if ext is None:
                return False
            else:
                try:
                    return 'TruNAS System : ' + ext.client[0].url.split('/')[2]
                except:
                    return 'TruNAS System :'

        except Exception as ex:
            return str(ex).replace("'", "").replace("<", "").replace(">", "")

    def check_credential(self, vc_ip, usernName, password, port):
        try:

            try:
                ssl._create_default_https_context = ssl._create_unverified_context
            except AttributeError:
                print 'Error ssl'
            si = SmartConnect("https", vc_ip, int(port), usernName, password)
            if si is None:
                return False
            else:
                return True

        except requests.exceptions.ConnectionError:
            return 'Provided vCenter Hostname/IP and port are not valid. '
        except vim.fault.InvalidLogin:
            return 'Provided vCenter credentials are not valid.'
        except Exception:
            return 'Internal Error. Please contact support.'
