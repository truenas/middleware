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

from freenasUI.api.utils import FreeBasicAuthentication
from freenasUI.storage.models import Volume
from freenasUI.plugins.models import Plugins, Kmod
from freenasUI.jails.models import Jails, JailsConfiguration

from jsonrpc import jsonrpc_method

log = logging.getLogger("plugins.api_calls")

PLUGINS_API_VERSION = "2"


#
#    API utility functions
#
def __popen(cmd):
    return Popen(
        cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True, close_fds=True
    )


def __get_jailsconfiguration():
    jc = JailsConfiguration.objects.order_by("-id")[0]

    return jc


def __get_jails(jail_name=None):
    jails = []

    if jail_name:
        jail = Jails.objects.get(jail_host=jail_name)
        jails.append(jail)

    else:
        jails = Jails.objects.all()

    return jails


def __get_plugins_jail_info(plugin_id):
    jail = None

    plugin = Plugins.objects.filter(pk=plugin_id)
    if plugin:
        plugin = plugin[0]
        jail = Jails.objects.get(jail_host=plugin.plugin_jail)

        #
        # XXX Hackety hack hack! XXX
        #
        # jail_ipv4|jail_ipv6, if using DHCP or AUTOCONF, will be
        # prefixed with "DHCP:"  and "AUTOCONF:". Current plugins aren't
        # aware of this (nor do they really need to be), so we just pass
        # it the property that only has the IP address.
        #
        jail.jail_ipv4 = jail.jail_ipv4_addr
        jail.jail_ipv6 = jail.jail_ipv6_addr

    return jail


def __get_plugins_jail_path(plugin_id):
    jail_path = None

    jail_info = __get_plugins_jail_info(plugin_id)
    if jail_info:
        jc = __get_jailsconfiguration()
        if jc:
            jail_path = "%s/%s" % (jc.jc_path, jail_info.jail_host)

    return jail_path


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
#    Jail methods
#
@jsonrpc_method("jails.jailsconfiguration.get")
def __jails_jailsconfiguration_get(request):
    return __serialize([__get_jailsconfiguration()])


@jsonrpc_method("jails.jails.get")
def __jails_jails_get(request, jail_name=None):
    return __serialize([__get_jails(jail_name)])


#
#    Plugins methods
#
@jsonrpc_method("plugins.plugins.get")
def __plugins_plugins_get(request, plugin_name=None):
    if plugin_name:
        return __serialize(Plugins.objects.filter(plugin_name=plugin_name))
    else:
        return __serialize(Plugins.objects.order_by("-pk"))


@jsonrpc_method("plugins.jail.info")
def __plugins_jail_info(request, plugin_id=None):
    return __serialize([__get_plugins_jail_info(plugin_id)])


@jsonrpc_method("plugins.jail.path")
def __plugins_jail_path(request, plugin_id=None):
    return __get_plugins_jail_path(plugin_id)


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

        # Fall back and check for API authentication
        http_auth = sessionid.decode('base64')
        # Simulate a request object required for FreeBasicAuthentication
        request = type(
            'request',
            (object, ),
            {'META': {'HTTP_AUTHORIZATION': http_auth}}
        )

        if FreeBasicAuthentication().is_authenticated(request):
            user = request.user
        else:
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
    for v in Volume.objects.all():
        mp_path = '/mnt/%s' % v.vol_name
        path_list.append(mp_path)
        datasets = v.get_datasets()

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
def __fs_mount_filesystem(request, plugin_id, src, dst):
    jail_path = __get_plugins_jail_path(plugin_id)
    if not jail_path:
        data = {
            "error": True,
            "message": "source or destination not specified",
        }
        return data

    if not src or not dst:
        data = {
            "error": True,
            "message": "source or destination not specified",
        }
        return data

    full_dst = "%s/%s" % (jail_path, dst)
    p = __popen("/sbin/mount_nullfs %s %s" % (src, full_dst))
    stdout, stderr = p.communicate()

    return {
        'error': False if p.returncode == 0 else True,
        'message': stderr,
    }


@jsonrpc_method("fs.umount")
def __fs_umount_filesystem(request, plugin_id, dst):
    jail_path = __get_plugins_jail_path(plugin_id)
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


@jsonrpc_method("fs.linprocfs")
def __fs_mount_filesystem_linprocfs(request, plugin_id, dst):
    jail_path = __get_plugins_jail_path(plugin_id)
    if not jail_path:
        data = {
            "error": True,
            "message": "source or destination not specified",
        }
        return data

    if not dst:
        data = {
            "error": True,
            "message": "destination not specified",
        }
        return data

    full_dst = "%s/%s" % (jail_path, dst)
    p = __popen("/sbin/mount -t linprocfs linprocfs %s" % (full_dst))
    stdout, stderr = p.communicate()

    return {
        'error': False if p.returncode == 0 else True,
        'message': stderr,
    }


#
#    OS methods
#
@jsonrpc_method("os.query")
def __os_query_system(request):
    return __api_call_not_implemented(request)


@jsonrpc_method("os.arch")
def os_arch(request):
    """
    Return the platform architecture

    Returns:
        str - ['amd64', 'i386']
    """
    pipe = Popen(
        "/usr/bin/uname -m",
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        shell=True,
        close_fds=True,
    )
    arch = pipe.communicate()[0]
    if pipe.returncode == 0:
        return arch


@jsonrpc_method("os.kldload")
def os_kldload(request, plugin_id, module):
    """
    Load a kernel module

    Returns: boolean
    """
    plugin = Plugins.objects.filter(pk=plugin_id)
    if plugin.exists() and not Kmod.objects.filter(
        plugin__id=plugin[0].id, module=module
    ).exists():
        Kmod.objects.create(
            plugin=plugin[0],
            module=module,
            order=None,
        )

    pipe = Popen([
        "/sbin/kldstat",
        "-n", module,
    ], stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
    pipe.communicate()
    if pipe.returncode == 0:
        return True

    pipe = Popen([
        "/sbin/kldload",
        module,
    ], stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
    pipe.communicate()
    return pipe.returncode == 0


#
#    Debug/Test/Null methods
#
@jsonrpc_method("api.test")
def __api_test(request):
    return True


@jsonrpc_method("api.debug")
def __api_debug(request):
    return True
