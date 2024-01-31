import pytest

from copy import deepcopy
from middlewared.plugins.filesystem_.utils import ACLType


NFS4_ACL = {'acl': [
    {
        'tag': 'GROUP',
        'id': 100,
        'perms': { 'BASIC': 'FULL_CONTROL' },
        'flags': {
            'FILE_INHERIT': True,
            'DIRECTORY_INHERIT': True,
            'INHERIT_ONLY': False,
            'NO_PROPAGATE_INHERIT': False,
            'INHERITED': False
        },
        'type': 'ALLOW'
    },
    {
        'tag': 'GROUP',
        'id': 200,
        'perms': { 'BASIC': 'MODIFY' },
        'flags': {
            'FILE_INHERIT': False,
            'DIRECTORY_INHERIT': True,
            'INHERIT_ONLY': False,
            'NO_PROPAGATE_INHERIT': False,
            'INHERITED': False
        },
        'type': 'ALLOW'
    },
    {
        'tag': 'GROUP',
        'id': 300,
        'perms': { 'BASIC': 'MODIFY' },
        'flags': {
            'FILE_INHERIT': True,
            'DIRECTORY_INHERIT': False,
            'INHERIT_ONLY': True,
            'NO_PROPAGATE_INHERIT': False,
            'INHERITED': False
        },
        'type': 'ALLOW'
    },
    {
        'tag': 'GROUP',
        'id': 400,
        'perms': { 'BASIC': 'MODIFY' },
        'flags': {
            'FILE_INHERIT': True,
            'DIRECTORY_INHERIT': True,
            'INHERIT_ONLY': True,
            'NO_PROPAGATE_INHERIT': True,
            'INHERITED': False
        },
        'type': 'ALLOW'
    },
    {
        'tag': 'GROUP',
        'id': 500,
        'perms': { 'BASIC': 'MODIFY' },
        'flags': {
            'FILE_INHERIT': False,
            'DIRECTORY_INHERIT': False,
            'INHERIT_ONLY': False,
            'NO_PROPAGATE_INHERIT': False,
            'INHERITED': False
        },
        'type': 'ALLOW'
    },
    {
        'tag': 'GROUP',
        'id': 600,
        'perms': { 'BASIC': 'MODIFY' },
        'flags': {
            'FILE_INHERIT': True,
            'DIRECTORY_INHERIT': True,
            'INHERIT_ONLY': False,
            'NO_PROPAGATE_INHERIT': True,
            'INHERITED': False
        },
        'type': 'ALLOW'
    },
], 'acltype': 'NFS4', 'trivial': False, 'uid': 0, 'gid': 0, 'path': '/mnt/dozer/SHARE'}


def test__nfs4_acl_inheritance():
    dir_inherited = ACLType.NFS4.calculate_inherited(deepcopy(NFS4_ACL), True)
    file_inherited = ACLType.NFS4.calculate_inherited(deepcopy(NFS4_ACL), False)

    for entry in dir_inherited:
        match entry['id']:
            case 100:
                expected = {
                    'FILE_INHERIT': True,
                    'DIRECTORY_INHERIT': True,
                    'INHERIT_ONLY': False,
                    'NO_PROPAGATE_INHERIT': False,
                    'INHERITED': True
                }
            case 200:
                expected = {
                    'FILE_INHERIT': False,
                    'DIRECTORY_INHERIT': True,
                    'INHERIT_ONLY': False,
                    'NO_PROPAGATE_INHERIT': False,
                    'INHERITED': True
                }
            case 300:
                expected = {
                    'FILE_INHERIT': True,
                    'DIRECTORY_INHERIT': False,
                    'INHERIT_ONLY': True,
                    'NO_PROPAGATE_INHERIT': False,
                    'INHERITED': True
                }
            case 400:
                expected = {
                    'FILE_INHERIT': True,
                    'DIRECTORY_INHERIT': True,
                    'INHERIT_ONLY': False,
                    'NO_PROPAGATE_INHERIT': True,
                    'INHERITED': True
                }
            case 600:
                expected = {
                    'FILE_INHERIT': False,
                    'DIRECTORY_INHERIT': False,
                    'INHERIT_ONLY': False,
                    'NO_PROPAGATE_INHERIT': False,
                    'INHERITED': True
                }
            case _:
                assert False, f'Unexpected entry: {entry["id"]}'

        assert entry['flags'] == expected, f'{entry["id"]}: flags do not match'

    for entry in file_inherited:
        match entry['id']:
            case 100:
                expected = {
                    'FILE_INHERIT': False,
                    'DIRECTORY_INHERIT': False,
                    'INHERIT_ONLY': False,
                    'NO_PROPAGATE_INHERIT': False,
                    'INHERITED': True
                }
            case 300:
                expected = {
                    'FILE_INHERIT': False,
                    'DIRECTORY_INHERIT': False,
                    'INHERIT_ONLY': False,
                    'NO_PROPAGATE_INHERIT': False,
                    'INHERITED': True
                }
            case 400:
                expected = {
                    'FILE_INHERIT': False,
                    'DIRECTORY_INHERIT': False,
                    'INHERIT_ONLY': False,
                    'NO_PROPAGATE_INHERIT': False,
                    'INHERITED': True
                }
            case 600:
                expected = {
                    'FILE_INHERIT': False,
                    'DIRECTORY_INHERIT': False,
                    'INHERIT_ONLY': False,
                    'NO_PROPAGATE_INHERIT': False,
                    'INHERITED': True
                }
            case _:
                assert False, f'Unexpected entry: {entry["id"]}'

        assert entry['flags'] == expected, f'{entry["id"]}: flags do not match'
