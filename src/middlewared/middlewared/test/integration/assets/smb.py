# -*- coding=utf-8 -*-
import contextlib
import logging
import os
import sys

from middlewared.test.integration.utils import call, ssh

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import ip as default_ip
except ImportError:
    default_ip = None

logger = logging.getLogger(__name__)

__all__ = ["smb_share", "smb_mount"]


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
    mount_cmd = [
        'mount.cifs', f'//{ip}/{share}', local_path,
        '-o', ','.join(mount_options)
    ]

    mount_string = ' '.join(mount_cmd)

    ssh(f'mkdir {local_path}; {mount_string}')

    try:
        yield local_path
    finally:
        ssh(f'umount {local_path}; rmdir {local_path}')
