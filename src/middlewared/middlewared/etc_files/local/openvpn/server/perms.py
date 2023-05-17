import errno
import os

from pathlib import Path

from middlewared.service import CallError


LOGS_FOLDER = '/var/log/openvpn'


def fix_perms(middleware):
    if nobody_user := middleware.call_sync('user.query', [('username', '=', 'nobody')]):
        nobody_uid = nobody_user[0]['uid']
        nobody_gid = nobody_user[0]['group']['bsdgrp_gid']
    else:
        raise CallError('Unable to locate "nobody" user', errno=errno.ENOENT)

    log_dir = Path(LOGS_FOLDER)
    log_dir.mkdir(parents=True, exist_ok=True)
    for path_attr in (
        log_dir, *map(lambda file_name: log_dir / file_name, ('openvpn.log', 'openvpn-status.log'))
    ):
        path_attr.touch(exist_ok=True)
        os.chown(path_attr.absolute().as_posix(), uid=nobody_uid, gid=nobody_gid)


def render(service, middleware):
    fix_perms(middleware)
