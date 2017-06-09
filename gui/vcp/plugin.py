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
import freenasUI.vcp.utils as utils
import configparser
import os
from django.conf import settings
from pyVmomi import vim
from configparser import SafeConfigParser
from pyVim.connect import SmartConnect


class PluginManager:

    property_file_path = settings.HERE + '/vcp/Extensionconfig.ini.dist'
    resurce_folder_path = settings.HERE + '/vcp/vcp_locales'
    privGroupName = 'iXSystems'

    def create_event_keyvalue_pairs(self):
        try:
            eri_list = []
            for file in os.listdir(self.resurce_folder_path):
                eri = vim.Extension.ResourceInfo()
                #Read locale file from vcp_locale
                eri.module = file.split("_")[0]
                file = open(self.resurce_folder_path + '/' + file, 'r')
                for line in file:
                    if len(line) > 2 and '=' in line:
                        if 'locale' in line:
                            eri.locale = line.split('=')[1].lstrip().rstrip()
                        else:
                            prop = line.split('=')
                            key_val = vim.KeyValue()
                            key_val.key = prop[0].lstrip().rstrip()
                            key_val.value = prop[1].lstrip().rstrip()
                            eri.data.append(key_val)
                file.close()
                eri_list.append(eri)
            return eri_list
        except Exception as ex:
            return 'can not read locales :' + str(ex)

    def get_extensionKey(self):
        cp = SafeConfigParser()
        cp.read(self.property_file_path)
        key = cp.get('RegisterParam', 'key')
        return key

    def get_extension(self, vcp_url, thumb_print):
        try:
            cp = SafeConfigParser()
            cp.read(self.property_file_path)
            company = cp.get('RegisterParam', 'company')
            descr = cp.get('RegisterParam', 'description')
            key = cp.get('RegisterParam', 'key')
            events = cp.get('RegisterParam', 'events').split(",")
            tasks = cp.get('RegisterParam', 'tasks').split(",")
            privs = cp.get('RegisterParam', 'auth').split(",")
            version = utils.get_plugin_version()
            if 'Not available' in version:
                return version
            label = cp.get('RegisterParam', 'label')
            sys_guiprotocol = vcp_url.split(':')[0]

            description = vim.Description()
            description.label = label
            description.summary = descr
            ext = vim.Extension()
            ext.company = company
            ext.version = version
            ext.key = key
            ext.description = description
            ext.lastHeartbeatTime = datetime.datetime.now()

            server_info = vim.Extension.ServerInfo()
            server_info.serverThumbprint = thumb_print
            server_info.type = sys_guiprotocol.upper()
            server_info.url = vcp_url
            server_info.description = description
            server_info.company = company
            server_info.adminEmail = ['ADMIN EMAIL']
            ext.server = [server_info]

            client = vim.Extension.ClientInfo()
            client.url = vcp_url
            client.company = company
            client.version = version
            client.description = description
            client.type = "vsphere-client-serenity"
            ext.client = [client]

            event_info = []
            for e in events:
                ext_event_type_info = vim.Extension.EventTypeInfo()
                ext_event_type_info.eventID = e
                event_info.append(ext_event_type_info)

            task_info = []
            for t in tasks:
                ext_type_info = vim.Extension.TaskTypeInfo()
                ext_type_info.taskID = t
                task_info.append(ext_type_info)

            #Register custom privileges required for vcp RBAC
            priv_info = []
            for priv in privs:
                ext_type_info = vim.Extension.PrivilegeInfo()
                ext_type_info.privID = priv
                ext_type_info.privGroupName = self.privGroupName
                priv_info.append(ext_type_info)

            ext.taskList = task_info
            ext.eventList = event_info
            ext.privilegeList = priv_info
            resource_list = self.create_event_keyvalue_pairs()
            if isinstance(resource_list, str):
                return resource_list
            ext.resourceList = resource_list

            return ext
        except configparser.NoOptionError as ex:
            return 'Property Missing : ' + str(ex)
        except Exception as ex:
            return str(ex).replace("'", "").replace("<", "").replace(">", "")

    def install_vCenter_plugin(
            self,
            vc_ip,
            usernName,
            password,
            port,
            vcp_url,
            thumb_print):
        try:
            try:
                ssl._create_default_https_context = ssl._create_unverified_context
            except AttributeError:
                print('Error ssl')
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
            context.verify_mode = ssl.CERT_NONE
            si = SmartConnect("https", vc_ip, int(port), usernName, password, sslContext=context)
            ext = self.get_extension(vcp_url, thumb_print)
            if isinstance(ext, vim.Extension):
                si.RetrieveServiceContent().extensionManager.RegisterExtension(ext)
                return True
            else:
                return ext

        except vim.fault.NoPermission as ex:
            return 'vCenter user has no permission to install the plugin.'

        except Exception as ex:
            return str(ex).replace("'", "").replace("<", "").replace(">", "")

    def uninstall_vCenter_plugin(self, vc_ip, usernName, password, port):
        try:
            try:
                ssl._create_default_https_context = ssl._create_unverified_context
            except AttributeError:
                print('Error ssl')
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
            context.verify_mode = ssl.CERT_NONE
            si = SmartConnect("https", vc_ip, int(port), usernName, password, sslContext=context)
            extkey = self.get_extensionKey()
            si.RetrieveServiceContent().extensionManager.UnregisterExtension(extkey)
            return True
        except vim.fault.NoPermission as ex:
            return 'vCenter user has no permission to uninstall the plugin.'
        except Exception as ex:
            return str(ex).replace("'", "").replace("<", "").replace(">", "")

    def upgrade_vCenter_plugin(
            self,
            vc_ip,
            usernName,
            password,
            port,
            vcp_url,
            thumb_print):
        try:
            try:
                ssl._create_default_https_context = ssl._create_unverified_context
            except AttributeError:
                print('Error ssl')
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
            context.verify_mode = ssl.CERT_NONE
            si = SmartConnect("https", vc_ip, int(port), usernName, password, sslContext=context)
            ext = self.get_extension(vcp_url, thumb_print)
            if isinstance(ext, vim.Extension):
                si.RetrieveServiceContent().extensionManager.UpdateExtension(ext)
                return True
            else:
                return ext
        except vim.fault.NoPermission as ex:
            return 'vCenter user has no permission to upgrade the plugin.'
        except Exception as ex:
            return str(ex).replace("'", "").replace("<", "").replace(">", "")

    def find_plugin(self, vc_ip, usernName, password, port):
        try:
            try:
                ssl._create_default_https_context = ssl._create_unverified_context
            except AttributeError:
                print('Error ssl')
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
            context.verify_mode = ssl.CERT_NONE
            si = SmartConnect("https", vc_ip, int(port), usernName, password, sslContext=context)
            extkey = self.get_extensionKey()
            ext = si.RetrieveServiceContent().extensionManager.FindExtension(extkey)
            if ext is None:
                return False
            else:
                try:
                    return 'TruNAS System : ' + ext.client[0].url.split('/')[2]
                except:
                    return 'TruNAS System :'
        except vim.fault.NoPermission as ex:
            return 'vCenter user does not have permission to perform this operation.'
        except Exception as ex:
            return str(ex).replace("'", "").replace("<", "").replace(">", "")

    def check_credential(self, vc_ip, usernName, password, port):
        try:

            try:
                ssl._create_default_https_context = ssl._create_unverified_context
            except AttributeError:
                print('Error ssl')
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
            context.verify_mode = ssl.CERT_NONE
            si = SmartConnect("https", vc_ip, int(port), usernName, password, sslContext=context)
            if si is None:
                return False
            else:
                return True

        except requests.exceptions.ConnectionError:
            return 'Provided vCenter Hostname/IP and port are not valid. '
        except vim.fault.InvalidLogin:
            return 'Provided vCenter credentials are not valid.'
        except vim.fault.NoPermission as ex:
            return 'vCenter user does not have permission to perform this operation.'
        except Exception:
            return 'Internal Error. Please contact support.'
