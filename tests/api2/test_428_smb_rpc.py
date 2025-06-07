import os

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from protocols import MS_RPC


SMB_USER = "smbrpcuser"
SMB_PWD = "smb1234#!@"
INVALID_SHARE_NAME_CHARACTERS = {'%', '<', '>', '*', '?', '|', '/', '\\', '+', '=', ';', ':', '"', ',', '[', ']'}


@pytest.fixture(scope="module")
def setup_smb_share(request):
    with dataset('rpc_test', data={'share_type': 'SMB'}) as ds:
        with smb_share(os.path.join('/mnt', ds), "RPC_TEST", {
            "access_based_share_enumeration": True, "purpose": "LEGACY_SHARE"
        }) as s:
            yield {'dataset': ds, 'share': s}


@pytest.fixture(autouse=True, scope="function")
def setup_smb_user(request):
    with user({
        "username": SMB_USER,
        "full_name": SMB_USER,
        "group_create": True,
        "home": "/var/empty",
        "password": SMB_PWD,
    }) as u:
        yield u


def test_001_net_share_enum(setup_smb_user, setup_smb_share):
    path = setup_smb_share['share']['path']
    share_name = setup_smb_share['share']['name']

    with MS_RPC(username=SMB_USER, password=SMB_PWD) as hdl:
        shares = hdl.shares()
        assert len(shares) == 2, str(shares)
        assert shares[0]['netname'] == share_name
        assert shares[0]['path'].replace('\\', '/')[2:] == path
        # IPC$ share should always be present
        assert shares[1]['netname'] == 'IPC$'
        assert shares[1]['path'] == 'C:\\var\\empty'


def test_002_enum_users(setup_smb_user, setup_smb_share):
    payload = {
        'query-filters': [['username', '=', SMB_USER]],
        'query-options': {
            'get': True,
            'extra': {'additional_information': ['SMB']}
        }
    }
    user_info = call('user.query', payload['query-filters'], payload['query-options'])
    with MS_RPC(username=SMB_USER, password=SMB_PWD) as hdl:
        entry = None
        users = hdl.users()
        for u in users:
            if u['user'] != SMB_USER:
                continue

            entry = u
            break

        assert entry is not None, str(users)
        rid = int(user_info['sid'].rsplit('-', 1)[1])
        assert rid == entry['rid'], str(entry)


def test_003_access_based_share_enum(setup_smb_user, setup_smb_share):
    call('sharing.smb.setacl', {
        'share_name': "RPC_TEST",
        'share_acl': [
            {
                'ae_who_sid': 'S-1-5-32-544',
                'ae_perm': 'FULL',
                'ae_type': 'ALLOWED'
            }
        ]
    })
    results = call("sharing.smb.query")
    with MS_RPC(username=SMB_USER, password=SMB_PWD) as hdl:
        shares = hdl.shares()
        assert len(shares) == 1, str({"enum": shares, "shares": results})


def test_share_name_restricutions(setup_smb_share):
    first_share = setup_smb_share['share']
    ds_name = setup_smb_share['dataset']

    for char in INVALID_SHARE_NAME_CHARACTERS:
        # First try updating existing share's name
        with pytest.raises(ValidationErrors) as ve:
            call('sharing.smb.update', first_share['id'], {'name': f'CANARY{char}'})

        assert 'share name contains the following invalid characters' in ve.value.errors[0].errmsg

        # Now try creating new share
        with pytest.raises(ValidationErrors) as ve:
            call('sharing.smb.create', {'path': os.path.join('/mnt', ds_name), 'name': f'CANARY{char}'})

        assert 'share name contains the following invalid characters' in ve.value.errors[0].errmsg


    with pytest.raises(ValidationErrors) as ve:
        call('sharing.smb.update', first_share['id'], {'name': 'CANARY\x85'})

    assert 'share name contains unicode control characters' in ve.value.errors[0].errmsg

    with pytest.raises(ValidationErrors) as ve:
        call('sharing.smb.create', {'path': os.path.join('/mnt', ds_name), 'name': 'CANARY\x85'})

    assert 'share name contains unicode control characters' in ve.value.errors[0].errmsg
