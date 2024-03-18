# -*- coding=utf-8 -*-
import contextlib
import logging
import os
import shlex
import sys

from base64 import b64encode, b64decode
from middlewared.test.integration.utils import call, ssh
from time import sleep

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import ip as default_ip
except ImportError:
    default_ip = None

logger = logging.getLogger(__name__)

__all__ = ["get_stream", "set_stream", "smb_share", "smb_mount"]

STREAM_PREFIX = 'user.DosStream.'
STREAM_SUFFIX = ':$DATA'
STREAM_SUFFIX_ESC = ':\\$DATA'


@contextlib.contextmanager
def smb_share(path, name, options=None):
    share = call("sharing.smb.create", {
        "path": path,
        "name": name,
        **(options or {})
    })
    assert call("service.start", "cifs")

    try:
        yield share
    finally:
        call("sharing.smb.delete", share["id"])
        call("service.stop", "cifs")


@contextlib.contextmanager
def smb_mount(share, username, password, local_path='/mnt/cifs', options=None, ip=default_ip):
    mount_options = [f'username={username}', f'password={password}'] + (options or [])
    escaped_path = shlex.quote(local_path)
    mount_cmd = [
        'mount.cifs', f'//{ip}/{share}', escaped_path,
        '-o', ','.join(mount_options)
    ]

    mount_string = ' '.join(mount_cmd)

    ssh(f'mkdir {escaped_path}; {mount_string}')

    try:
        yield local_path
    finally:
        ssh(f'umount {escaped_path}; rmdir {local_path}')


def del_stream(filename, xat_name, mountpoint='/mnt/cifs'):
    local_path = os.path.join(mountpoint, filename)
    xat_name = f'{STREAM_PREFIX}{xat_name}{STREAM_SUFFIX_ESC}'
    cmd = 'python3 -c "import os;'
    cmd += f'os.removexattr(\\\"{local_path}\\\", \\\"{xat_name}\\\")"'
    results = ssh(cmd, complete_response=True, check=False)
    assert results['result'], f'cmd: {cmd}, result: {results["stderr"]}'


def list_stream(filename, mountpoint='/mnt/cifs'):
    local_path = os.path.join(mountpoint, filename)

    # Vertical bar is used as separator because it is a reserved character
    # over SMB and will never be present in stream name
    cmd = 'python3 -c "import os;'
    cmd += f'print(\\\"\\|\\\".join(os.listxattr(\\\"{local_path}\\\")))"'
    results = ssh(cmd, complete_response=True, check=False)
    assert results['result'], f'cmd: {cmd}, result: {results["stderr"]}'

    streams = []
    for entry in results['stdout'].strip().split('|'):
         if not entry.startswith(STREAM_PREFIX):
             continue

         entry = entry.split(STREAM_PREFIX)[1]
         assert entry.endswith(STREAM_SUFFIX)

         # slice off the suffix
         streams.append(entry[:-len(STREAM_SUFFIX)])

    return streams


def get_stream(filename, xat_name, mountpoint='/mnt/cifs'):
    """
    Retrieve binary data for an alternate data stream via the xattr handler on
    a SMB client mount via the remote TrueNAS server. The python script below uses
    the samba wrapper around getxattr due to limitations in os.getxattr regarding
    maximum xattr size.
    """
    local_path = os.path.join(mountpoint, filename)
    xat_name = f'{STREAM_PREFIX}{xat_name}{STREAM_SUFFIX_ESC}'
    cmd = 'python3 -c "from samba.xattr_native import wrap_getxattr; import base64;'
    cmd += f'print(base64.b64encode(wrap_getxattr(\\\"{local_path}\\\", \\\"{xat_name}\\\")).decode())"'
    results = ssh(cmd, complete_response=True, check=False)
    assert results['result'], f'cmd: {cmd}, result: {results["stderr"]}'

    return b64decode(results['stdout'])


def set_stream(filename, xat_name, data, mountpoint='/mnt/cifs'):
    """
    Write binary data for an alternate data stream via the xattr handler on
    a SMB client mount via the remote TrueNAS server. The python script below uses
    the samba wrapper around setxattr due to limitations in os.setxattr regarding
    maximum xattr size.
    """
    b64data = b64encode(data).decode()
    local_path = os.path.join(mountpoint, filename)
    xat_name = f'{STREAM_PREFIX}{xat_name}{STREAM_SUFFIX_ESC}'
    cmd = 'python3 -c "from samba.xattr_native import wrap_setxattr; import base64;'
    cmd += f'wrap_setxattr(\\\"{local_path}\\\", \\\"{xat_name}\\\", base64.b64decode(\\\"{b64data}\\\"))"'
    results = ssh(cmd, complete_response=True, check=False)
    assert results['result'], f'cmd: {cmd}, result: {results["stderr"]}'
