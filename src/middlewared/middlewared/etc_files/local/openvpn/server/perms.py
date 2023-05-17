import errno
import os

from pathlib import Path

from middlewared.service import CallError


def fix_perms(middleware):
    if nobody_user := middleware.call_sync('user.query', [('username', '=', 'nobody')]):
        nobody_uid = nobody_user[0]['uid']
        nobody_gid = nobody_user[0]['group']['bsdgrp_gid']
    else:
        raise CallError('Unable to locate "nobody" user', errno=errno.ENOENT)

    log_dir = Path('/var/log/openvpn')
    log_dir.mkdir(parents=True, exist_ok=True)
    os.chown(log_dir.absolute().as_posix(), uid=nobody_uid, gid=nobody_gid)
    for file_name in ('openvpn.log', 'openvpn-status.log'):
        file_attr = log_dir / file_name
        file_attr.touch(exist_ok=True)
        os.chown(file_attr.absolute().as_posix(), uid=nobody_uid, gid=nobody_gid)


def render(service, middleware):
    fix_perms(middleware)
