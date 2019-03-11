# -*- coding=utf-8 -*-
import enum
from bsd import acl

"""
These are simplified forms of permissions sets based
on NTFS basic permissions.
"""
class ACLWho(enum.Enum):
    USER_OBJ = 'owner@'
    GROUP_OBJ = 'group@'
    EVERYONE = 'everyone@'
    USER = 'USER'
    GROUP = 'GROUP'

def convert_to_basic_permset(permset):
    perm = 0
    for k, v, in permset.items():
        if v:
            perm |= acl.NFS4Perm[k]

    try:
        SimplePerm = (acl.NFS4BasicPermset(perm)).name
    except Exception:
        SimplePerm = 'OTHER'

    return SimplePerm

def convert_to_basic_flagset(flagset):
    flags = 0
    for k, v, in flagset.items():
        if k == "INHERITED":
            continue
        if v:
            flags |= acl.NFS4Flag[k]

    try:
        SimpleFlag = (acl.NFS4BasicFlagset(flags)).name
    except Exception:
        SimpleFlag = 'OTHER'

    return SimpleFlag

def convert_to_adv_permset(basic_perm):
    permset = {}
    perm_mask = acl.NFS4BasicPermset[basic_perm].value
    for name, member in acl.NFS4Perm.__members__.items():
        if perm_mask & member.value:
            permset.update({name: True})
        else: 
            permset.update({name: False})

    return permset

def convert_to_adv_flagset(basic_flag):
    flagset = {}
    flag_mask = acl.NFS4BasicFlagset[basic_flag].value
    for name, member in acl.NFS4Flag.__members__.items():
        if flag_mask & member.value:
            flagset.update({name: True})
        else:
            flagset.update({name: False})

    return flagset 
