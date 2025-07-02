# -*- coding=utf-8 -*-
import contextlib
import logging
import os
import shlex
import sys

from base64 import b64encode, b64decode
from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server


logger = logging.getLogger(__name__)

__all__ = [
    "copy_stream",
    "list_stream",
    "get_stream",
    "set_stream",
    "set_xattr_compat",
    "smb_share",
    "smb_mount"
]

STREAM_PREFIX = 'user.DosStream.'
STREAM_SUFFIX = ':$DATA'
STREAM_SUFFIX_ESC = ':\\$DATA'
SAMBA_COMPAT = '/proc/fs/cifs/stream_samba_compat'


@contextlib.contextmanager
def smb_share(path, name, options=None):
    share = call("sharing.smb.create", {
        "path": path,
        "name": name,
        **(options or {})
    })
    assert call("service.control", "START", "cifs", job=True)

    try:
        yield share
    finally:
        try:
            call("sharing.smb.delete", share["id"])
        except InstanceNotFound:
            # for some tests we delete the share
            # this should not cause an error
            pass

        call("service.control", "STOP", "cifs", job=True)


@contextlib.contextmanager
def smb_mount(share, username, password, local_path='/mnt/cifs', options=None, ip=None):
    ip = ip or truenas_server.ip
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


def set_xattr_compat(enable_status: bool) -> None:
    """
    Enable / disable samba compatibility byte for SMB client. See
    SMB client implementation notes.

    NOTE: this requires that at least one SMB share be mounted.
    """
    assert isinstance(enable_status, bool)
    val = 1 if enable_status is True else 0

    ssh(f'echo {val} > {SAMBA_COMPAT}')
    res = ssh(f'cat {SAMBA_COMPAT}')

    assert val == int(res.strip())


def copy_stream(
    filename: str,
    xat_name_from: str,
    xat_name_to: str,
    mountpoint='/mnt/cifs'
) -> None:
    """
    Duplicate one stream to another stream on the same file.
    This is used to validate that xattr handler works properly
    for large xattrs.

    NOTE: requires existing SMB client mount at `mountpoint`.
    """
    assert call('filesystem.statfs', mountpoint)['fstype'] == 'cifs'
    local_path = os.path.join(mountpoint, filename)

    xat_name_from = f'{STREAM_PREFIX}{xat_name_from}{STREAM_SUFFIX_ESC}'
    xat_name_to = f'{STREAM_PREFIX}{xat_name_to}{STREAM_SUFFIX_ESC}'

    cmd = 'python3 -c "from samba.xattr_native import wrap_getxattr, wrap_setxattr;'
    cmd += f'wrap_setxattr(\\\"{local_path}\\\", \\\"{xat_name_to}\\\", '
    cmd += f'wrap_getxattr(\\\"{local_path}\\\", \\\"{xat_name_from}\\\"))"'
    results = ssh(cmd, complete_response=True, check=False)
    assert results['result'], f'cmd: {cmd}, result: {results["stderr"]}'


def del_stream(
    filename: str,
    xat_name: str,
    mountpoint='/mnt/cifs'
) -> None:
    """
    Delete the alternate data stream with name `xat_name` from
    the specified file.

    NOTE: requires existing SMB client mount at `mountpoint`.
    """
    assert call('filesystem.statfs', mountpoint)['fstype'] == 'cifs'
    local_path = os.path.join(mountpoint, filename)
    xat_name = f'{STREAM_PREFIX}{xat_name}{STREAM_SUFFIX_ESC}'
    cmd = 'python3 -c "import os;'
    cmd += f'os.removexattr(\\\"{local_path}\\\", \\\"{xat_name}\\\")"'
    results = ssh(cmd, complete_response=True, check=False)
    assert results['result'], f'cmd: {cmd}, result: {results["stderr"]}'


def list_stream(
    filename: str,
    mountpoint='/mnt/cifs'
) -> list:
    """
    Return list of alternate data streams contained by the specified
    file. Stream prefix and suffix will be stripped from return.

    NOTE: requires existing SMB client mount at `mountpoint`.
    """
    assert call('filesystem.statfs', mountpoint)['fstype'] == 'cifs'
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


def get_stream(
    filename: str,
    xat_name: str,
    mountpoint='/mnt/cifs'
) -> bytes:
    """
    Retrieve binary data for an alternate data stream via the xattr handler on
    a SMB client mount via the remote TrueNAS server. The python script below uses
    the samba wrapper around getxattr due to limitations in os.getxattr regarding
    maximum xattr size.

    NOTE: requires existing SMB client mount at `mountpoint`.
    """
    assert call('filesystem.statfs', mountpoint)['fstype'] == 'cifs'
    local_path = os.path.join(mountpoint, filename)
    xat_name = f'{STREAM_PREFIX}{xat_name}{STREAM_SUFFIX_ESC}'
    cmd = 'python3 -c "from samba.xattr_native import wrap_getxattr; import base64;'
    cmd += f'print(base64.b64encode(wrap_getxattr(\\\"{local_path}\\\", \\\"{xat_name}\\\")).decode())"'
    results = ssh(cmd, complete_response=True, check=False)
    assert results['result'], f'cmd: {cmd}, result: {results["stderr"]}'

    return b64decode(results['stdout'])


def set_stream(
    filename: str,
    xat_name: str,
    data: bytes,
    mountpoint='/mnt/cifs'
) -> None:
    """
    Write binary data for an alternate data stream via the xattr handler on
    a SMB client mount via the remote TrueNAS server. The python script below uses
    the samba wrapper around setxattr due to limitations in os.setxattr regarding
    maximum xattr size.

    NOTE: requires existing SMB client mount at `mountpoint`.
    """
    assert call('filesystem.statfs', mountpoint)['fstype'] == 'cifs'
    b64data = b64encode(data).decode()
    local_path = os.path.join(mountpoint, filename)
    xat_name = f'{STREAM_PREFIX}{xat_name}{STREAM_SUFFIX_ESC}'
    cmd = 'python3 -c "from samba.xattr_native import wrap_setxattr; import base64;'
    cmd += f'wrap_setxattr(\\\"{local_path}\\\", \\\"{xat_name}\\\", base64.b64decode(\\\"{b64data}\\\"))"'
    results = ssh(cmd, complete_response=True, check=False)
    assert results['result'], f'cmd: {cmd}, result: {results["stderr"]}'
