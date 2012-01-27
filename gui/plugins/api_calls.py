#+
# Copyright 2012 iXsystems, Inc.
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

import os
import sys
import json

from subprocess import Popen, PIPE

from django.core import serializers

from freenasUI import account, network, plugins, services, sharing, storage, system


PLUGINS_API_VERSION = "0.1"


#
#    API utility functions
#
def __popen(cmd):
    return Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True, close_fds=True)


def __get_plugins_jail_info():
    jail_info = services.models.Plugins.objects.order_by("-id")
    return jail_info[0] if jail_info else None


def __get_plugins_jail_path():
    jail_path = None
    jail_info = __get_plugins_jail_info()
    if jail_info:
        jail_path = jail_info.jail_path
    return jail_path

    
def __get_plugins_jail_name():
    jail_name = None
    jail_info = __get_plugins_jail_info()
    if jail_info:
        jail_name = jail_info.jail_name 
    return jail_name    


def __get_plugins_jail_full_path():
    jail_name = None
    jail_name = __get_plugins_jail_name()
    if not jail_name:
        return None

    jail_path = None
    jail_path = __get_plugins_jail_path()
    if not jail_path:
        return None

    jail_full_path = os.path.join(jail_path, jail_name)
    return jail_full_path

def __serialize(objects):
    return serializers.serialize("json", objects)

def __api_call_not_implemented(request, **kwargs):
    data = {}
    data["error"] = False
    data["message"] = "not implemented"
    return json.dumps(data)




class PluginInterface(object):
    def _m(self, t):
        return "%s_%s_%s" % (self._system, t, self._name)
        
    def __init__(self, system, name, model):
        self._system = system
        self._name = name
        self._model = model

        self._method_names = [
            "get",
            "set",
            "create",
            "destroy",
            "info",
            "status"
        ]

        self._interface = {}
        for i in self._method_names:
            self._interface[self._m(i)] = (getattr(self, i), self)
 
    def get(self, request, **kwargs):
        return __api_call_not_implemented(request, kwargs)
    def set(self, request, **kwargs):
        return __api_call_not_implemented(request, kwargs)
    def create(self, request, **kwargs):
        return __api_call_not_implemented(request, kwargs)
    def destroy(self, request, **kwargs):
        return __api_call_not_implemented(request, kwargs)
    def info(self, request, **kwargs):
        return __api_call_not_implemented(request, kwargs)
    def status(self, request, **kwargs):
        return __api_call_not_implemented(request, kwargs)

    def interface(self):
        return self._interface


#
#    API information methods
#
def __api_call_api_methods(request, **kwargs):
    api_methods = __plugins_api_call_table.keys()
    data = { "error": False, "api_methods": sorted(api_methods) }
    return json.dumps(data)


def __api_call_api_version(request, **kwargs):
    data = { "error": False, "api_version": PLUGINS_API_VERSION }
    return json.dumps(data)


#
#    Account methods
#
class AccountbsdGroupsAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class AccountbsdUsersAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class AccountbsdGroupMembershipAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))



#
#    Network methods
#
class NetworkGlobalConfigurationAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class NetworkInterfacesAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class NetworkAliasAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class NetworkVLANAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class NetworkLAGGInterfaceAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class NetworkLAGGInterfaceMembersAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class NetworkStaticRouteAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))


#
#    Plugins methods
#
class PluginsPluginsAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))



#
#    Services methods
#
class ServicesServicesAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesCIFSAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesAFPAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesNFSAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesiSCSITargetGlobalConfigurationAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesiSCSITargetExtentAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesiSCSITargetPortalAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesiSCSITargetAuthorizedInitiatorAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesiSCSITargetAuthCredentialAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesiSCSITargetAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesiSCSITargetToExtentAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesDynamicDNSAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesPluginsAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesSNMPAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesUPSAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesFTPAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesTFTPAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesSSHAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesActiveDirectoryAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesLDAPAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesRsyncdAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesRsyncModAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class ServicesSMARTAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))



#
#    Sharing methods
#
class SharingCIFS_ShareAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class SharingAFP_ShareAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class SharingNFS_ShareAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))



#
#    Storage methods
#
class StorageVolumeAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class StorageDiskAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class StorageMountPointAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class StorageReplRemoteAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class StorageReplicationAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class StorageTaskAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))



#
#    System methods
#
class SystemSettingsAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class SystemNTPServerAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class SystemAdvancedAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class SystemEmailAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class SystemSSLAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class SystemCronJobAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class SystemRsyncAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class SystemSMARTTestAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class SystemSysctlAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))

class SystemTunableAPI(PluginInterface):
    def get(self, request, **kwargs):
        return __serialize(self._model.objects.order_by("-id"))



#
#    Database methods
#
def __api_call_db_query_database(request, **kwargs):
    data = { "error": False, "message": "Not implemented" }
    return json.dumps(data)



#
#    Filesystem methods
#
def __api_call_fs_get_mountpoints(request, **kwargs):
    path_list = []
    mp_list = storage.models.MountPoint.objects.exclude(
        mp_volume__vol_fstype__exact='iscsi').select_related().all()

    for mp in mp_list: 
        path_list.append(mp.mp_path)
        datasets = mp.mp_volume.get_datasets()

        if datasets:
            for name, dataset in datasets.items():
                path_list.append(dataset.mountpoint)

    data = { "error": False, "mountpoints": path_list }
    return json.dumps(data)

def __api_call_fs_mount_filesystem(request, **kwargs):
    jail_path = __get_plugins_jail_full_path()
    if not jail_path:
        data = { "error": True, "message": "plugins jail is not configured" }
        return json.dumps(data)

    src = kwargs.get("source", None)
    dst = kwargs.get("destination", None)

    if not src or not dst:
        data = { "error": True, "message": "source or destination not specified" }
        return json.dumps(data)

    full_dst = os.path.join(jail_path, dst)
    p = __popen("/sbin/mount_nullfs %s %s" % (src, full_dst))
    p.wait()

    out = p.communicate()[0].split('\n')
    if p.returncode != 0:
        data = { "error": True, "message": out }

    else:
        data = { "error": False, "message": "ok" }

    return json.dumps(data)

def __api_call_fs_umount_filesystem(request, **kwargs):
    jail_path = __get_plugins_jail_full_path()
    if not jail_path:
        data = { "error": True, "message": "plugins jail is not configured" }
        return json.dumps(data)

    dst = kwargs.get("destination", None)
    if not dst:
        data = { "error": True, "message": "destination not specified" }
        return json.dumps(data)

    fs = os.path.join(jail_path, dst)
    p = __popen("/sbin/umount %s" % fs)
    p.wait()

    out = p.communicate()[0].split('\n')
    if p.returncode != 0:
        data = { "error": True, "message": out }

    else:
        data = { "error": False, "message": "ok" }

    return json.dumps(data)



#
#    Debug/Test/Null methods
#
def __api_call_api_test(request, **kwargs):
    kwargs["error"] = False
    return json.dumps(kwargs)

def __api_call_api_debug(request, **kwargs):
    kwargs["error"] = False
    return json.dumps(kwargs)



#
#    API call dispatch table
#
__plugins_api_call_table = {}


#
#    Account
#
__plugins_api_call_table.update(AccountbsdGroupsAPI(
    "account", "bsdgroups", account.models.bsdGroups).interface()
)
__plugins_api_call_table.update(AccountbsdUsersAPI(
    "account", "bsdusers", account.models.bsdUsers).interface()
)
__plugins_api_call_table.update(AccountbsdGroupMembershipAPI(
    "account", "bsdgroupmembership", account.models.bsdGroupMembership).interface()
)


#
#    Network
#
__plugins_api_call_table.update(NetworkGlobalConfigurationAPI(
    "network", "globalconfiguration", network.models.GlobalConfiguration).interface()
)
__plugins_api_call_table.update(NetworkInterfacesAPI(
    "network", "interfaces", network.models.Interfaces).interface()
)
__plugins_api_call_table.update(NetworkAliasAPI(
    "network", "alias", network.models.Alias).interface()
)
__plugins_api_call_table.update(NetworkVLANAPI(
    "network", "vlan", network.models.VLAN).interface()
)
__plugins_api_call_table.update(NetworkLAGGInterfaceAPI(
    "network", "lagginterface", network.models.LAGGInterface).interface()
)
__plugins_api_call_table.update(NetworkLAGGInterfaceMembersAPI(
    "network", "lagginterfacemembers", network.models.LAGGInterfaceMembers).interface()
)
__plugins_api_call_table.update(NetworkStaticRouteAPI(
    "network", "staticroute", network.models.StaticRoute).interface()
)


#
#    Plugins
#
__plugins_api_call_table.update(PluginsPluginsAPI(
    "plugins", "plugins", plugins.models.Plugins).interface()
)


#
#    Services
#
__plugins_api_call_table.update(ServicesServicesAPI(
    "services", "services", services.models.services).interface()
)
__plugins_api_call_table.update(ServicesCIFSAPI(
    "services", "cifs", services.models.CIFS).interface()
)
__plugins_api_call_table.update(ServicesAFPAPI(
    "services", "afp", services.models.AFP).interface()
)
__plugins_api_call_table.update(ServicesNFSAPI(
    "services", "nfs", services.models.NFS).interface()
)
__plugins_api_call_table.update(ServicesiSCSITargetGlobalConfigurationAPI(
    "services", "iscsitargetglobalconfiguration", services.models.iSCSITargetGlobalConfiguration).interface()
)
__plugins_api_call_table.update(ServicesiSCSITargetExtentAPI(
    "services", "iscsitargetextent", services.models.iSCSITargetExtent).interface()
)
__plugins_api_call_table.update(ServicesiSCSITargetPortalAPI(
    "services", "iscsitargetportal", services.models.iSCSITargetPortal).interface()
)
__plugins_api_call_table.update(ServicesiSCSITargetAuthorizedInitiatorAPI(
    "services", "iscsitargetauthorizedinitiator", services.models.iSCSITargetAuthorizedInitiator).interface()
)
__plugins_api_call_table.update(ServicesiSCSITargetAuthCredentialAPI(
    "services", "iscsitargetauthcredential", services.models.iSCSITargetAuthCredential).interface()
)
__plugins_api_call_table.update(ServicesiSCSITargetAPI(
    "services", "iscsitarget", services.models.iSCSITarget).interface()
)
__plugins_api_call_table.update(ServicesiSCSITargetToExtentAPI(
    "services", "iscsitargettoextent", services.models.iSCSITargetToExtent).interface()
)
__plugins_api_call_table.update(ServicesDynamicDNSAPI(
    "services", "dynamicdns", services.models.DynamicDNS).interface()
)
__plugins_api_call_table.update(ServicesPluginsAPI(
    "services", "plugins", services.models.Plugins).interface()
)
__plugins_api_call_table.update(ServicesSNMPAPI(
    "services", "snmp", services.models.SNMP).interface()
)
__plugins_api_call_table.update(ServicesUPSAPI(
    "services", "ups", services.models.UPS).interface()
)
__plugins_api_call_table.update(ServicesFTPAPI(
    "services", "ftp", services.models.FTP).interface()
)
__plugins_api_call_table.update(ServicesTFTPAPI(
    "services", "tftp", services.models.TFTP).interface()
)
__plugins_api_call_table.update(ServicesSSHAPI(
    "services", "ssh", services.models.SSH).interface()
)
__plugins_api_call_table.update(ServicesActiveDirectoryAPI(
    "services", "activedirectory", services.models.ActiveDirectory).interface()
)
__plugins_api_call_table.update(ServicesLDAPAPI(
    "services", "ldap", services.models.LDAP).interface()
)
__plugins_api_call_table.update(ServicesRsyncdAPI(
    "services", "rsyncd", services.models.Rsyncd).interface()
)
__plugins_api_call_table.update(ServicesRsyncModAPI(
    "services", "rsyncmod", services.models.RsyncMod).interface()
)
__plugins_api_call_table.update(ServicesSMARTAPI(
    "services", "smart", services.models.SMART).interface()
)


#
#    Sharing
#
__plugins_api_call_table.update(SharingCIFS_ShareAPI(
    "sharing", "cifs_share", sharing.models.CIFS_Share).interface()
)
__plugins_api_call_table.update(SharingAFP_ShareAPI(
    "sharing", "afp_share", sharing.models.AFP_Share).interface()
)
__plugins_api_call_table.update(SharingNFS_ShareAPI(
    "sharing", "nfs_share", sharing.models.NFS_Share).interface()
)


#
#    Storage methods
#
__plugins_api_call_table.update(StorageVolumeAPI(
    "storage", "volume", storage.models.Volume).interface()
)
__plugins_api_call_table.update(StorageDiskAPI(
    "storage", "disk", storage.models.Disk).interface()
)
__plugins_api_call_table.update(StorageMountPointAPI(
    "storage", "mountpoint", storage.models.MountPoint).interface()
)
__plugins_api_call_table.update(StorageReplRemoteAPI(
    "storage", "replremote", storage.models.ReplRemote).interface()
)
__plugins_api_call_table.update(StorageReplicationAPI(
    "storage", "replication", storage.models.Replication).interface()
)
__plugins_api_call_table.update(StorageTaskAPI(
    "storage", "task", storage.models.Task).interface()
)


#
#    System
#
__plugins_api_call_table.update(SystemSettingsAPI(
    "system", "settings", system.models.Settings).interface()
)
__plugins_api_call_table.update(SystemNTPServerAPI(
    "system", "ntpserver", system.models.NTPServer).interface()
)
__plugins_api_call_table.update(SystemAdvancedAPI(
    "system", "advanced", system.models.Advanced).interface()
)
__plugins_api_call_table.update(SystemEmailAPI(
    "system", "email", system.models.Email).interface()
)
__plugins_api_call_table.update(SystemSSLAPI(
    "system", "ssl", system.models.SSL).interface()
)
__plugins_api_call_table.update(SystemCronJobAPI(
    "system", "cronjob", system.models.CronJob).interface()
)
__plugins_api_call_table.update(SystemRsyncAPI(
    "system", "rsync", system.models.Rsync).interface()
)
__plugins_api_call_table.update(SystemSMARTTestAPI(
    "system", "smarttest", system.models.SMARTTest).interface()
)
__plugins_api_call_table.update(SystemSysctlAPI(
    "system", "sysctl", system.models.Sysctl).interface()
)
__plugins_api_call_table.update(SystemTunableAPI(
    "system", "tunable", system.models.Tunable).interface()
)


#
#    API
#
__plugins_api_call_table.update(
    { "api_methods": (__api_call_api_methods, None) }
)
__plugins_api_call_table.update(
    { "api_version": (__api_call_api_version, None) }
)
__plugins_api_call_table.update(
    { "api_authenticate": (__api_call_api_version, None) }
)


#
#    Database
#
__plugins_api_call_table.update(
    { "db_query_database": (__api_call_db_query_database, None) }
)


#
#    Filesystem
#
__plugins_api_call_table.update(
    { "fs_get_mountpoints": (__api_call_fs_get_mountpoints, None) }
)
__plugins_api_call_table.update(
    { "fs_mount_filesystem": (__api_call_fs_mount_filesystem, None) }
)
__plugins_api_call_table.update(
    { "fs_umount_filesystem":( __api_call_fs_umount_filesystem, None) }
)


#
#    Debug/Test
#
__plugins_api_call_table.update(
    { "test": (__api_call_api_test, None) }
)
__plugins_api_call_table.update(
    { "debug":( __api_call_api_debug, None) }
)


def plugins_api_get_info(name):
    method = None
    try:
        info = __plugins_api_call_table[name]

    except:
        info = __plugins_api_call_table["test"]

    return info
