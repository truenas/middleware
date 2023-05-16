import errno
import os

from middlewared.service import CallError


LOGS_FOLDER = '/var/log/openvpn'


def fix_perms(middleware):
    if nobody_user := middleware.call_sync('user.query', [('username', '=', 'nobody')]):
        nobody_uid = nobody_user[0]['uid']
        nobody_gid = nobody_user[0]['group']['bsdgrp_gid']
    else:
        raise CallError('Unable to locate "nobody" user', errno=errno.ENOENT)

    os.makedirs(LOGS_FOLDER, exist_ok=True)
    for path in (
        LOGS_FOLDER, *map(lambda file: os.path.join(LOGS_FOLDER, file), ('openvpn.log', 'openvpn-status.log'))
    ):
        if not os.path.exists(path):
            with open(path, 'w'):
                pass
        if os.stat(path).st_uid != nobody_uid or os.stat(path).st_gid != nobody_gid:
            os.chown(path, uid=nobody_uid, gid=nobody_gid)


def render(service, middleware):
    fix_perms(middleware)
