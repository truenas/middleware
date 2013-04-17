#i+
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

from subprocess import Popen, PIPE
import logging
import os

from django.conf import settings
from django.core import serializers
from django.contrib import auth
from django.utils.importlib import import_module

from freenasUI import plugins, services, storage

from jsonrpc import jsonrpc_method

log = logging.getLogger("plugins.api_calls")

PLUGINS_API_VERSION = "1"


#
#    API utility functions
#
def __popen(cmd):
    return Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
        shell=True,
        close_fds=True)


def __get_plugins_jail_info():
    pass
#    jail_info = services.models.PluginsJail.objects.order_by("-pk")
#    return jail_info[0] if jail_info else None


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


def __api_call_not_implemented(request):
    return "not implemented"


#
#    API information methods
#
@jsonrpc_method("api.version")
def __api_call_api_version(request):
    return PLUGINS_API_VERSION


#
#    Plugins methods
#
@jsonrpc_method("plugins.plugins.get")
def __plugins_plugins_get(request, plugin_name=None):
    if plugin_name:
        return __serialize(plugins.models.Plugins.objects.filter(
            plugin_name=plugin_name))
    else:
        return __serialize(plugins.models.Plugins.objects.order_by("-pk"))


@jsonrpc_method("plugins.jail.info")
def __plugins_jail_info(request):
    return __serialize([__get_plugins_jail_info()])


@jsonrpc_method("plugins.is_authenticated")
def plugins_is_authenticated(request, sessionid):
    """
    Given a sessionid, check whether it is authenticated
    and valid (not expired)

    Returns:
        bool
    """
    engine = import_module(settings.SESSION_ENGINE)
    session = engine.SessionStore(sessionid)

    try:
        user_id = session[auth.SESSION_KEY]
        backend_path = session[auth.BACKEND_SESSION_KEY]
        backend = auth.load_backend(backend_path)
        user = backend.get_user(user_id)
    except KeyError:
        return False
    if user and user.is_authenticated():
        return True
    return False


#
#    Filesystem methods
#
@jsonrpc_method("fs.mountpoints.get")
def __fs_mountpoints_get(request):
    path_list = []
    mp_list = storage.models.MountPoint.objects.exclude(
        mp_volume__vol_fstype__exact='iscsi').select_related().all()

    for mp in mp_list:
        path_list.append(mp.mp_path)
        datasets = mp.mp_volume.get_datasets()

        if datasets:
            for name, dataset in datasets.items():
                path_list.append(dataset.mountpoint)

    return path_list


@jsonrpc_method("fs.mounted.get")
def __fs_mounted_get(request, path=None):
    path_list = []

    cmd = "/sbin/mount -p"
    if path:
        cmd += " | /usr/bin/awk '/%s/ { print $0; }'" % path.replace("/", "\/")

    p = __popen(cmd)
    lines = p.communicate()[0].strip().split('\n')
    for line in lines:
        if not line:
            continue
        parts = line.split()
        if path and parts:
            dst = parts[1]
            i = dst.find(path)
            dst = dst[i:]
            parts[1] = dst
        path_list.append(parts)

    if p.returncode != 0:
        return None

    return path_list


@jsonrpc_method("fs.mount")
def __fs_mount_filesystem(request, src, dst):
    jail_path = __get_plugins_jail_full_path()
    if not jail_path:
        data = {"error": True,
            "message": "source or destination not specified"}
        return data

    if not src or not dst:
        data = {"error": True,
            "message": "source or destination not specified"}
        return data

    full_dst = "%s/%s" % (jail_path, dst)
    p = __popen("/sbin/mount_nullfs %s %s" % (src, full_dst))
    stdout, stderr = p.communicate()

    return {
        'error': False if p.returncode == 0 else True,
        'message': stderr,
        }


@jsonrpc_method("fs.umount")
def __fs_umount_filesystem(request, dst):
    jail_path = __get_plugins_jail_full_path()
    if not jail_path:
        data = {"error": True, "message": "plugins jail is not configured"}
        return data

    if not dst:
        data = {"error": True, "message": "destination not specified"}
        return data

    fs = "%s/%s" % (jail_path, dst)
    p = __popen("/sbin/umount %s" % fs)
    p.wait()

    return False if p.returncode != 0 else True


@jsonrpc_method("fs.directory.get")
def __fs_get_directory(request, path=None):
    files = None
    if path:
        files = os.listdir(path)
    return files


@jsonrpc_method("fs.file.get")
def __fs_get_file(request, path=None):
    if not path:
        raise ValueError

    with open(path, "r") as f:
        content = f.read()

    return content


#
#    OS methods
#
@jsonrpc_method("os.query")
def  __os_query_system(request):
    return __api_call_not_implemented(request)


@jsonrpc_method("os.arch")
def os_arch(request):
    """
    Return the platform architecture

    Returns:
        str - ['amd64', 'i386']
    """
    pipe = Popen("/usr/bin/uname -m", stdin=PIPE, stdout=PIPE, stderr=PIPE,
        shell=True, close_fds=True)
    arch = pipe.communicate()[0]
    if pipe.returncode == 0:
        return arch


#
#    Debug/Test/Null methods
#
@jsonrpc_method("api.test")
def __api_test(request):
    return True


@jsonrpc_method("api.debug")
def __api_debug(request):
    return True
