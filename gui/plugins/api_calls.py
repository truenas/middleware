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




#
#    API information methods
#
def __api_call_api_methods(request, **kwargs):
    api_methods = __plugins_api_call_table.keys()
    data = { "api_methods": sorted(api_methods) }
    return json.dumps(data)


def __api_call_api_version(request, **kwargs):
    data = { "error": False, "api_version": PLUGINS_API_VERSION }
    return json.dumps(data)


#
#    Account methods
#
def __api_call_account_get_bsdgroups(self, **kwargs):
    return __serialize(account.models.bsdGroups.objects.order_by("-id"))

def __api_call_account_get_bsdusers(self, **kwargs):
    return __serialize(account.models.bsdUsers.objects.order_by("-id"))



#
#    Network methods
#
def __api_call_network_get_globalconfiguration(request, **kwargs):
    return __serialize(network.models.GlobalConfiguration.objects.order_by("-id"))

def __api_call_network_get_interfaces(request, **kwargs):
    return __serialize(network.models.Interfaces.objects.order_by("-id"))

def __api_call_network_get_alias(request, **kwargs):
    return __serialize(network.models.Alias.objects.order_by("-id"))

def __api_call_network_get_vlan(request, **kwargs):
    return __serialize(network.models.VLAN.objects.order_by("-id"))

def __api_call_network_get_lagginterface(request, **kwargs):
    return __serialize(network.models.LAGGInterface.objects.order_by("-id"))

def __api_call_network_get_staticroute(request, **kwargs):
    return __serialize(network.models.StaticRoute.objects.order_by("-id"))



#
#    Plugins methods
#
def __api_call_plugins_get_plugins(request, **kwargs):
    return __serialize(plugins.models.Plugins.objects.order_by("-id"))



#
#    Services methods
#
def __api_call_services_get_services(request, **kwargs):
    return __serialize(services.models.services.objects.order_by("-id"))

def __api_call_services_get_cifs(request, **kwargs):
    return __serialize(services.models.CIFS.objects.order_by("-id"))

def __api_call_services_get_afp(request, **kwargs):
    return __serialize(services.models.AFP.objects.order_by("-id"))

def __api_call_services_get_nfs(request, **kwargs):
    return __serialize(services.models.NFS.objects.order_by("-id"))

def __api_call_services_get_iscsitargetglobalconfiguration(request, **kwargs):
    return __serialize(services.models.iSCSITargetGlobalConfiguration.objects.order_by("-id"))

def __api_call_services_get_iscsitargetextent(request, **kwargs):
    return __serialize(services.models.iSCSITargetExtent.objects.order_by("-id"))

def __api_call_services_get_iscsitargetauthorizedinitiator(request, **kwargs):
    return __serialize(services.models.iSCSITargetAuthorizedInitiator.objects.order_by("-id"))

def __api_call_services_get_iscsitargetauthcredential(request, **kwargs):
    return __serialize(services.models.iSCSITargetAuthCredential.objects.order_by("-id"))

def __api_call_services_get_iscsitarget(request, **kwargs):
    return __serialize(services.models.iSCSITarget.objects.order_by("-id"))

def __api_call_services_get_dynamicdns(request, **kwargs):
    return __serialize(services.models.DynamicDNS.objects.order_by("-id"))

def __api_call_services_get_plugins(request, **kwargs):
    return __serialize(services.models.Plugins.objects.order_by("-id"))

def __api_call_services_get_snmp(request, **kwargs):
    return __serialize(services.models.SNMP.objects.order_by("-id"))

def __api_call_services_get_ups(request, **kwargs):
    return __serialize(services.models.UPS.objects.order_by("-id"))

def __api_call_services_get_ftp(request, **kwargs):
    return __serialize(services.models.FTP.objects.order_by("-id"))

def __api_call_services_get_tftp(request, **kwargs):
    return __serialize(services.models.TFTP.objects.order_by("-id"))

def __api_call_services_get_ssh(request, **kwargs):
    return __serialize(services.models.SSH.objects.order_by("-id"))

def __api_call_services_get_activedirectory(request, **kwargs):
    return __serialize(services.models.ActiveDirectory.objects.order_by("-id"))

def __api_call_services_get_ldap(request, **kwargs):
    return __serialize(services.models.LDAP.objects.order_by("-id"))

def __api_call_services_get_rsyncd(request, **kwargs):
    return __serialize(services.models.Rsyncd.objects.order_by("-id"))

def __api_call_services_get_rsyncmod(request, **kwargs):
    return __serialize(services.models.RsyncMod.objects.order_by("-id"))

def __api_call_services_get_smart(request, **kwargs):
    return __serialize(services.models.SMART.objects.order_by("-id"))


#
#    Sharing methods
#
def __api_call_sharing_get_cifs_share(request, **kwargs):
    return __serialize(sharing.models.CIFS_Share.objects.order_by("-id"))

def __api_call_sharing_get_afp_share(request, **kwargs):
    return __serialize(sharing.models.AFP_Share.objects.order_by("-id"))

def __api_call_sharing_get_nfs_share(request, **kwargs):
    return __serialize(sharing.models.NFS_Share.objects.order_by("-id"))



#
#    Storage methods
#
def __api_call_get_volume(request, **kwargs):
    return __serialize(storage.models.Volume.objects.order_by("-id"))

def __api_call_get_disk(request, **kwargs):
    return __serialize(storage.models.Disk.objects.order_by("-id"))

def __api_call_get_mountpoint(request, **kwargs):
    return __serialize(storage.models.MountPoint.objects.order_by("-id"))

def __api_call_get_replremote(request, **kwargs):
    return __serialize(storage.models.ReplRemote.objects.order_by("-id"))

def __api_call_get_replication(request, **kwargs):
    return __serialize(storage.models.Replication.objects.order_by("-id"))

def __api_call_get_task(request, **kwargs):
    return __serialize(storage.models.Task.objects.order_by("-id"))




#
#    System methods
#
def __api_call_system_get_settings(request, **kwargs):
    return __serialize(system.models.Settings.objects.order_by("-id"))

def __api_call_system_get_ntpserver(request, **kwargs):
    return __serialize(system.models.NTPServer.objects.order_by("-id"))

def __api_call_system_get_advanced(request, **kwargs):
    return __serialize(system.models.Advanced.objects.order_by("-id"))

def __api_call_system_get_email(request, **kwargs):
    return __serialize(system.models.Email.objects.order_by("-id"))

def __api_call_system_get_ssl(request, **kwargs):
    return __serialize(system.models.SSL.objects.order_by("-id"))

def __api_call_system_get_cronjob(request, **kwargs):
    return __serialize(system.models.CronJob.objects.order_by("-id"))

def __api_call_system_get_rsync(request, **kwargs):
    return __serialize(system.models.Rsync.objects.order_by("-id"))

def __api_call_system_get_smarttest(request, **kwargs):
    return __serialize(system.models.SMARTTest.objects.order_by("-id"))

def __api_call_system_get_sysctl(request, **kwargs):
    return __serialize(system.models.Sysctl.objects.order_by("-id"))

def __api_call_system_get_tunable(request, **kwargs):
    return __serialize(system.models.Tunable.objects.order_by("-id"))



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

def __api_call_not_implemented(request, **kwargs):
    data = {}
    data["error"] = False
    data["message"] = "not implemented"
    return json.dumps(data)



#
#    API call dispatch table
#
__plugins_api_call_table = {

    #
    #    Account
    #
    "account_get_bsdgroups":                          __api_call_account_get_bsdgroups,
    "account_set_bsdgroups":                          __api_call_not_implemented,

    "account_get_bsdusers":                           __api_call_account_get_bsdusers,
    "account_set_bsdusers":                           __api_call_not_implemented,


    #
    #    Network
    #
    "network_get_globalconfiguration":                __api_call_network_get_globalconfiguration,
    "network_set_globalconfiguration":                __api_call_not_implemented,

    "network_get_interfaces":                         __api_call_network_get_interfaces,
    "network_set_interfaces":                         __api_call_not_implemented,

    "network_get_alias":                              __api_call_network_get_alias,
    "network_set_alias":                              __api_call_not_implemented,

    "network_get_vlan":                               __api_call_network_get_vlan,
    "network_set_vlan":                               __api_call_not_implemented,

    "network_get_lagginterface":                      __api_call_network_get_lagginterface,
    "network_set_lagginterface":                      __api_call_not_implemented,

    "network_get_staticroute":                        __api_call_network_get_staticroute,
    "network_set_staticroute":                        __api_call_not_implemented,


    #
    #    Plugins
    #
    "plugins_get_plugins":                            __api_call_plugins_get_plugins,
    "plugins_set_plugins":                            __api_call_not_implemented,


    #
    #    Services
    #
    "services_get_services":                          __api_call_services_get_services,
    "services_set_services":                          __api_call_not_implemented,

    "services_get_cifs":                              __api_call_services_get_cifs,
    "services_set_cifs":                              __api_call_not_implemented,

    "services_get_afp":                               __api_call_services_get_afp,
    "services_set_afp":                               __api_call_not_implemented,

    "services_get_nfs":                               __api_call_services_get_nfs,
    "services_set_nfs":                               __api_call_not_implemented,

    "services_get_iscsitargetglobalconfiguration":    __api_call_services_get_iscsitargetglobalconfiguration,
    "services_set_iscsitargetglobalconfiguration":    __api_call_not_implemented,

    "services_get_iscsitargetextent":                 __api_call_services_get_iscsitargetextent,
    "services_set_iscsitargetextent":                 __api_call_not_implemented,

    "services_get_iscsitargetauthorizedinitiator":    __api_call_services_get_iscsitargetauthorizedinitiator,
    "services_set_iscsitargetauthorizedinitiator":    __api_call_not_implemented,

    "services_get_iscsitargetauthcredential":         __api_call_services_get_iscsitargetauthcredential,
    "services_set_iscsitargetauthcredential":         __api_call_not_implemented,

    "services_get_iscsitarget":                       __api_call_services_get_iscsitarget,
    "services_set_iscsitarget":                       __api_call_not_implemented,

    "services_get_dynamicdns":                        __api_call_services_get_dynamicdns,
    "services_set_dynamicdns":                        __api_call_not_implemented,

    "services_get_plugins":                           __api_call_services_get_plugins,
    "services_set_plugins":                           __api_call_not_implemented,

    "services_get_snmp":                              __api_call_services_get_snmp,
    "services_set_snmp":                              __api_call_not_implemented,

    "services_get_ups":                               __api_call_services_get_ups,
    "services_set_ups":                               __api_call_not_implemented,

    "services_get_ftp":                               __api_call_services_get_ftp,
    "services_set_ftp":                               __api_call_not_implemented,

    "services_get_tftp":                              __api_call_services_get_tftp,
    "services_set_tftp":                              __api_call_not_implemented,

    "services_get_ssh":                               __api_call_services_get_ssh,
    "services_set_ssh":                               __api_call_not_implemented,

    "services_get_activedirectory":                   __api_call_services_get_activedirectory,
    "services_set_activedirectory":                   __api_call_not_implemented,

    "services_get_ldap":                              __api_call_services_get_ldap,
    "services_set_ldap":                              __api_call_not_implemented,

    "services_get_rsyncd":                            __api_call_services_get_rsyncd,
    "services_set_rsyncd":                            __api_call_not_implemented,

    "services_get_rsyncmod":                          __api_call_services_get_rsyncmod,
    "services_set_rsyncmod":                          __api_call_not_implemented,

    "services_get_smart":                             __api_call_services_get_smart,
    "services_set_smart":                             __api_call_not_implemented,


    #
    #    Sharing
    #
    "sharing_get_cifs_share":                         __api_call_sharing_get_cifs_share,
    "sharing_set_cifs_share":                         __api_call_not_implemented,

    "sharing_get_afp_share":                          __api_call_sharing_get_afp_share,
    "sharing_set_afp_share":                          __api_call_not_implemented,

    "sharing_get_nfs_share":                          __api_call_sharing_get_nfs_share,
    "sharing_set_nfs_share":                          __api_call_not_implemented,


    #
    #    Storage methods
    #
    "storage_get_volume":                             __api_call_get_volume,
    "storage_set_volume":                             __api_call_not_implemented,

    "storage_get_disk":                               __api_call_get_disk,
    "storage_set_disk":                               __api_call_not_implemented,

    "storage_get_mountpoint":                         __api_call_get_mountpoint,
    "storage_set_mountpoint":                         __api_call_not_implemented,

    "storage_get_replremote":                         __api_call_get_replremote,
    "storage_set_replremote":                         __api_call_not_implemented,

    "storage_get_replication":                        __api_call_get_replication,
    "storage_set_replication":                        __api_call_not_implemented,

    "storage_get_task":                               __api_call_get_task,
    "storage_set_task":                               __api_call_not_implemented,


    #
    #    System
    #
    "system_get_settings":                            __api_call_system_get_settings,
    "system_set_settings":                            __api_call_not_implemented,

    "system_get_ntpserver":                           __api_call_system_get_ntpserver,
    "system_set_ntpserver":                           __api_call_not_implemented,

    "system_get_advanced":                            __api_call_system_get_advanced,
    "system_set_advanced":                            __api_call_not_implemented,

    "system_get_email":                               __api_call_system_get_email,
    "system_set_email":                               __api_call_not_implemented,

    "system_get_ssl":                                 __api_call_system_get_ssl,
    "system_set_ssl":                                 __api_call_not_implemented,

    "system_get_cronjob":                             __api_call_system_get_cronjob,
    "system_set_cronjob":                             __api_call_not_implemented,

    "system_get_rsync":                               __api_call_system_get_rsync,
    "system_set_rsync":                               __api_call_not_implemented,

    "system_get_smarttest":                           __api_call_system_get_smarttest,
    "system_set_smarttest":                           __api_call_not_implemented,

    "system_get_sysctl":                              __api_call_system_get_sysctl,
    "system_set_sysctl":                              __api_call_not_implemented,

    "system_get_tunable":                             __api_call_system_get_tunable,
    "system_set_tunable":                             __api_call_not_implemented,


    #
    #    API
    #
    "api_methods":                                    __api_call_api_methods,
    "api_version":                                    __api_call_api_version,


    #
    #    Database
    #
    "db_query_database":                              __api_call_db_query_database,


    #
    #    Filesystem
    #
    "fs_get_mountpoints":                             __api_call_fs_get_mountpoints,
    "fs_mount_filesystem":                            __api_call_fs_mount_filesystem,
    "fs_umount_filesystem":                           __api_call_fs_umount_filesystem,


    #
    #    Debug/Test
    #
    "test":                                           __api_call_api_test,
    "debug":                                          __api_call_api_debug
}


def plugins_api_get_method(name):
    method = None
    try:
        method = __plugins_api_call_table[name]

    except:
        method = __api_call_api_test

    return method
