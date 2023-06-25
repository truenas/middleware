#!/usr/bin/env python3

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import (ip, dev_test, pool_name)
from functions import GET, POST
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from protocols import MS_RPC

reason = 'Skipping for test development testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)

SMB_USER = "smbrpcuser"
SMB_PWD = "smb1234#!@"

@pytest.fixture(scope="module")
def setup_smb_share(request):
    with dataset('rpc_test', data={'share_type': 'SMB'}) as ds:
        with smb_share(os.path.join('/mnt', ds), "RPC_TEST", {"abe": True, "purpose": "NO_PRESET"}) as s:
            yield {'dataset': ds, 'share': s}

@pytest.fixture(autouse=True, scope="function")
def setup_smb_user(request):
    with user({
        "username": SMB_USER,
        "full_name": SMB_USER,
        "group_create": True,
        "home": "/nonexistent",
        "password": SMB_PWD,
    }) as u:
        yield u


def test_001_net_share_enum(setup_smb_user, setup_smb_share):
    path = setup_smb_share['share']['path']
    share_name = setup_smb_share['share']['name']

    with MS_RPC(username=SMB_USER, password=SMB_PWD, host=ip) as hdl:
        shares = hdl.shares()
        # IPC$ share should always be present
        assert len(shares) == 2, str(shares)
        assert shares[0]['netname'] == 'IPC$'
        assert shares[0]['path'] == 'C:\\tmp'
        assert shares[1]['netname'] == share_name
        assert shares[1]['path'].replace('\\', '/')[2:] == path


def test_002_enum_users(setup_smb_user, setup_smb_share):
    results = GET('/user', payload={
        'query-filters': [['username', '=', SMB_USER]],
        'query-options': {
            'get': True,
            'extra': {'additional_information': ['SMB']}
        }
    })
    assert results.status_code == 200, results.text
    user_info = results.json()

    with MS_RPC(username=SMB_USER, password=SMB_PWD, host=ip) as hdl:
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
    payload = {
        'share_name': "RPC_TEST",
        'share_acl': [
            {
                'ae_who_sid': 'S-1-5-32-544',
                'ae_perm': 'FULL',
                'ae_type': 'ALLOWED'
            }
        ]
    }
    results = POST("/sharing/smb/setacl", payload)
    assert results.status_code == 200, results.text

    results = GET("/sharing/smb")
    assert results.status_code == 200, results.text

    with MS_RPC(username=SMB_USER, password=SMB_PWD, host=ip) as hdl:
        shares = hdl.shares()
        assert len(shares) == 1, str({"enum": shares, "shares": results.json()})
