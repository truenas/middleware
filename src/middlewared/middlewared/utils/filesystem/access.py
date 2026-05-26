import os
from typing import Any

from middlewared.service_exception import CallError
from middlewared.utils.nss import grp, pwd

# This should be a sufficiently high UID to never be used explicitly
# We need one for doing access checks based on groups
SYNTHETIC_UID = 2 ** 32 - 2


def get_user_details(id_type: str, xid: int) -> dict[str, Any] | None:
    if id_type not in ['USER', 'GROUP']:
        raise CallError(f'{id_type}: invalid ID type. Must be "USER" or "GROUP"')

    if not isinstance(xid, int):
        raise TypeError(f'{type(xid)}: xid must be int.')

    if id_type == 'USER':
        try:
            u = pwd.getpwuid(xid)
            out = {
                'pw_name': u.pw_name,
                'pw_uid': u.pw_uid,
                'pw_gid': u.pw_gid,
                'pw_gecos': u.pw_gecos,
                'pw_dir': u.pw_dir,
                'pw_shell': u.pw_shell,
            }
            out['grouplist'] = os.getgrouplist(u.pw_name, u.pw_gid)
            out['id_name'] = out['pw_name']
            return out
        except KeyError:
            return None

    try:
        g = grp.getgrgid(xid)
        grp_obj = {
            'gr_name': g.gr_name,
            'gr_gid': g.gr_gid,
            'gr_mem': g.gr_mem
        }
    except KeyError:
        return None

    return {
        'pw_name': 'synthetic_user',
        'pw_uid': SYNTHETIC_UID,
        'pw_gid': grp_obj['gr_gid'],
        'pw_gecos': 'synthetic user',
        'pw_dir': '/var/empty',
        'pw_shell': '/usr/bin/zsh',
        'grouplist': [grp_obj['gr_gid']],
        'id_name': grp_obj['gr_name']
    }
