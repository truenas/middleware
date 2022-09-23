#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
import json
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST, wait_on_job
from auto_config import ip, pool_name, password, user, dev_test
from pytest_dependency import depends
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')

DATASET = f"{pool_name}/smb-reg"
DATASET_URL = DATASET.replace('/', '%2F')
SMB_NAME = "REGISTRYTEST"
SMB_PATH = "/mnt/" + DATASET
SHARES = [f'{SMB_NAME}_{i}' for i in range(0, 25)]
SHARE_DICT = {}
PRESETS = [
    "DEFAULT_SHARE",
    "ENHANCED_TIMEMACHINE",
    "MULTI_PROTOCOL_NFS",
    "PRIVATE_DATASETS",
    "WORM_DROPBOX"
]
DETECTED_PRESETS = None

"""
Note: following sample auxiliary parameters and comments were
provided by a community member for testing. They do not represent
the opinion or recommendation of iXsystems.
"""
SAMPLE_AUX = [
    'follow symlinks = yes ',
    'veto files = /.windows/.mac/.zfs/',
    '# needed explicitly for each share to prevent default being set',
    'admin users = MY_ACCOUNT',
    '## NOTES:', '',
    "; aio-fork might cause smbd core dump/signal 6 in log in v11.1- see bug report [https://redmine.ixsystems.com/issues/27470]. Looks helpful but disabled until clear if it's responsible.", '', '',
    '### VFS OBJECTS (shadow_copy2 not included if no periodic snaps, so do it manually)', '',
    '# Include recycle, crossrename, and exclude readonly, as share=RW', '',
    '#vfs objects = zfs_space zfsacl winmsa streams_xattr recycle shadow_copy2 crossrename aio_pthread', '',
    'vfs objects = aio_pthread streams_xattr shadow_copy_zfs acl_xattr crossrename winmsa recycle', '',
    '# testing without shadow_copy2', '',
    'valid users = MY_ACCOUNT @ALLOWED_USERS',
    'invalid users = root anonymous guest',
    'hide dot files = yes',
]


@pytest.mark.dependency(name="SMB_DATASET_CREATED")
def test_001_creating_smb_DATASET(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        "name": DATASET,
        "share_type": "SMB"
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


def test_002_changing_dataset_permissions_of_smb_dataset(request):
    """
    ACL must be stripped from our test dataset in order
    to successfully test all presets.
    """
    depends(request, ["SMB_DATASET_CREATED"])
    global job_id
    payload = {
        'acl': [],
        'mode': '777',
        'group': 'nogroup',
        'user': 'nobody',
        'options': {'stripacl': True, 'recursive': True}
    }
    results = POST(f"/pool/dataset/id/{DATASET_URL}/permission/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()


@pytest.mark.dependency(name="ACL_SET")
def test_003_verify_the_job_id_is_successful(request):
    depends(request, ["SMB_DATASET_CREATED"])
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.mark.dependency(name="SHARES_CREATED")
@pytest.mark.parametrize('smb_share', SHARES)
def test_004_creating_a_smb_share_path(request, smb_share):
    """
    Create large set of SMB shares for testing registry.
    """
    depends(request, ["SMB_DATASET_CREATED", "ACL_SET"])
    global SHARE_DICT

    target = f'{SMB_PATH}/{smb_share}'
    results = POST('/filesystem/mkdir', target)
    assert results.status_code == 200, results.text

    payload = {
        "comment": "My Test SMB Share",
        "path": target,
        "home": False,
        "name": smb_share,
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']
    SHARE_DICT[smb_share] = smb_id


def test_005_shares_in_registry(request):
    depends(request, ["SHARES_CREATED", "ssh_password"], scope="session")
    cmd = 'midclt call sharing.smb.reg_listshares'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    reg_shares = json.loads(results['output'].strip())
    for smb_share in SHARES:
        assert smb_share in reg_shares


@pytest.mark.parametrize('smb_share', SHARES)
def test_006_rename_shares(request, smb_share):
    depends(request, ["SHARES_CREATED"])
    results = PUT(f"/sharing/smb/id/{SHARE_DICT[smb_share]}/",
                  {"name": f"NEW_{smb_share}"})
    assert results.status_code == 200, results.text


def test_007_renamed_shares_in_registry(request):
    """
    Share renames need to be explicitly tested because
    it will actually result in share being removed from
    registry and re-added with different name.
    """
    depends(request, ["SHARES_CREATED", "ssh_password"], scope="session")
    cmd = 'midclt call sharing.smb.reg_listshares'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    reg_shares = json.loads(results['output'].strip())
    for smb_share in SHARES:
        assert f'NEW_{smb_share}' in reg_shares
    assert len(reg_shares) == len(SHARES)


@pytest.mark.parametrize('preset', PRESETS)
def test_008_test_presets(request, preset):
    """
    This test iterates through SMB share presets,
    applies them to a single share, and then validates
    that the preset was applied correctly.

    In case of bool in API, simple check that appropriate
    value is set in return from sharing.smb.update will
    be sufficient. In case of auxiliary parameters, we
    need to be a bit more thorough. The preset will not
    be reflected in returned auxsmbconf and so we'll need
    to directly reach out and run smb.getparm.
    """
    depends(request, ["SHARES_CREATED", "ssh_password"], scope="session")
    global DETECTED_PRESETS
    if not DETECTED_PRESETS:
        results = GET("/sharing/smb/presets")
        assert results.status_code == 200, results.text
        DETECTED_PRESETS = results.json()

    to_test = DETECTED_PRESETS[preset]['params']
    to_test_aux = to_test['auxsmbconf']
    results = PUT(f'/sharing/smb/id/{SHARE_DICT["REGISTRYTEST_0"]}/',
                  {"purpose": preset})
    assert results.status_code == 200, results.text

    assert results.status_code == 200, results.text
    new_conf = results.json()
    for entry in to_test_aux.splitlines():
        aux, val = entry.split('=', 1)
        cmd = f'midclt call smb.getparm "{aux.strip()}" {new_conf["name"]}'
        results = SSH_TEST(cmd, user, password, ip)
        assert results['result'] is True, f"[{entry}]: {results['output']}"
        assert val.strip() == results['output'].strip()

    for k in to_test.keys():
        if k == "auxsmbconf":
            continue
        assert to_test[k] == new_conf[k]


def test_009_reset_smb(request):
    """
    Remove all parameters that might turn us into
    a MacOS-style SMB server (fruit).
    """
    depends(request, ["SHARES_CREATED"])
    results = PUT(f'/sharing/smb/id/{SHARE_DICT["REGISTRYTEST_0"]}/',
                  {"purpose": "NO_PRESET", "timemachine": False})
    assert results.status_code == 200, results.text

    payload = {"aapl_extensions": False}
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_010_test_aux_param_on_update(request):
    depends(request, ["SHARES_CREATED", "ssh_password"], scope="session")
    results = GET(
        '/sharing/smb', payload={
            'query-filters': [['id', '=', SHARE_DICT["REGISTRYTEST_0"]]],
            'query-options': {'get': True},
        }
    )
    assert results.status_code == 200, results.text
    old_aux = results.json()['auxsmbconf']
    results = PUT(f'/sharing/smb/id/{SHARE_DICT["REGISTRYTEST_0"]}/',
                  {"auxsmbconf": '\n'.join(SAMPLE_AUX)})
    assert results.status_code == 200, results.text
    new_aux = results.json()['auxsmbconf']
    new_name = results.json()['name']
    ncomments_sent = 0
    ncomments_recv = 0

    for entry in old_aux.splitlines():
        """
        Verify that aux params from last preset applied
        are still in effect. Parameters included in
        SAMPLE_AUX will never be in a preset so risk of
        collision is minimal.
        """
        aux, val = entry.split('=', 1)
        cmd = f'midclt call smb.getparm "{aux.strip()}" {new_name}'
        results = SSH_TEST(cmd, user, password, ip)
        assert results['result'] is True, f"[{entry}]: {results['output']}"
        out = results['output'].strip()
        inval = val.strip()
        # list cant be compared if item are not in the same place
        # converting to set have a valid comparison.
        assert set(inval) == set(out), f"[{entry}]: {out}"

    for entry in new_aux.splitlines():
        """
        Verify that non-comment parameters were successfully
        applied to the running configuration.
        """
        if not entry:
            continue

        if entry.startswith(('#', ';')):
            ncomments_recv += 1
            continue

        aux, val = entry.split('=', 1)
        cmd = f'midclt call smb.getparm "{aux.strip()}" {new_name}'
        results = SSH_TEST(cmd, user, password, ip)
        assert results['result'] is True, f"[{entry}]: {results['output']}"
        out = results['output'].strip()
        inval = val.strip()
        if aux.strip() == "vfs objects":
            new_obj = inval.split()
            # list cant be compared if item are not in the same place
            # converting to set have a valid comparison.
            assert set(new_obj) == set(json.loads(out)), f"[{entry}]: {out}"
        else:
            assert inval == out, f"[{entry}]: {out}"

    """
    Verify comments aren't being stripped on update
    """
    for entry in SAMPLE_AUX:
        if entry.startswith(('#', ';')):
            ncomments_sent += 1

    assert ncomments_sent == ncomments_recv, new_aux


def test_011_test_aux_param_on_create(request):
    depends(request, ["SHARES_CREATED", "ssh_password"], scope="session")
    smb_share = "AUX_CREATE"

    target = f'{SMB_PATH}/{smb_share}'
    results = POST('/filesystem/mkdir', target)
    assert results.status_code == 200, results.text

    payload = {
        "comment": "My Test SMB Share",
        "path": target,
        "home": False,
        "name": smb_share,
        "purpose": "ENHANCED_TIMEMACHINE",
        "auxsmbconf": '\n'.join(SAMPLE_AUX)
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']
    new_aux = results.json()['auxsmbconf']
    new_name = results.json()['name']

    pre_aux = DETECTED_PRESETS["ENHANCED_TIMEMACHINE"]["params"]["auxsmbconf"]
    ncomments_sent = 0
    ncomments_recv = 0

    for entry in pre_aux.splitlines():
        """
        Verify that aux params from preset were applied
        successfully to the running configuration.
        """
        aux, val = entry.split('=', 1)
        cmd = f'midclt call smb.getparm "{aux.strip()}" {new_name}'
        results = SSH_TEST(cmd, user, password, ip)
        assert results['result'] is True, f"[{entry}]: {results['output']}"
        out = results['output'].strip()
        inval = val.strip()
        # list cant be compared if item are not in the same place
        # converting to set have a valid comparison.
        assert set(inval) == set(out), f"[{entry}]: {out}"

    for entry in new_aux.splitlines():
        """
        Verify that non-comment parameters were successfully
        applied to the running configuration.
        """
        if not entry:
            continue

        if entry.startswith(('#', ';')):
            ncomments_recv += 1
            continue

        aux, val = entry.split('=', 1)
        cmd = f'midclt call smb.getparm "{aux.strip()}" {new_name}'
        results = SSH_TEST(cmd, user, password, ip)
        assert results['result'] is True, f"[{entry}]: {results['output']}"
        out = results['output'].strip()
        inval = val.strip()
        if aux.strip() == "vfs objects":
            new_obj = inval.split()
            # list cant be compared if item are not in the same place
            # converting to set have a valid comparison.
            assert set(new_obj) == set(json.loads(out)), f"[{entry}]: {out}"
        else:
            assert inval == out, f"[{entry}]: {out}"

    """
    Verify comments aren't being stripped on update
    """
    for entry in SAMPLE_AUX:
        if entry.startswith(('#', ';')):
            ncomments_sent += 1

    assert ncomments_sent == ncomments_recv, new_aux
    results = DELETE(f"/sharing/smb/id/{smb_id}")
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('smb_share', SHARES)
def test_012_delete_shares(request, smb_share):
    depends(request, ["SHARES_CREATED"])
    results = DELETE(f"/sharing/smb/id/{SHARE_DICT[smb_share]}")
    assert results.status_code == 200, results.text


def test_013_registry_is_empty(request):
    depends(request, ["SHARES_CREATED", "ssh_password"], scope="session")
    cmd = 'midclt call sharing.smb.reg_listshares'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    reg_shares = json.loads(results['output'].strip())
    assert len(reg_shares) == 0, results['output']


def test_014_config_is_empty(request):
    depends(request, ["SHARES_CREATED"])
    results = GET(
        '/sharing/smb', payload={
            'query-filters': [],
            'query-options': {'count': True},
        }
    )
    assert results.status_code == 200, results.text
    assert results.json() == 0, results.text


"""
Following battery of tests validate behavior of registry
with regard to homes shares
"""


@pytest.mark.dependency(name="HOME_SHARE_CREATED")
def test_015_create_homes_share(request):
    depends(request, ["SMB_DATASET_CREATED"])
    smb_share = "HOME_CREATE"
    global home_id

    target = f'{SMB_PATH}/{smb_share}'
    results = POST('/filesystem/mkdir', target)
    assert results.status_code == 200, results.text

    payload = {
        "comment": "My Test SMB Share",
        "path": target,
        "home": True,
        "purpose": "NO_PRESET",
        "name": smb_share,
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    home_id = results.json()['id']


def test_016_verify_homeshare_in_registry(request):
    """
    When the "home" checkbox is checked, the share
    _must_ be added to the SMB running configuration with
    the name "homes". This is a share name has special
    behavior in Samba. This test verifies that the
    share was added to the configuration with the
    correct name.
    """
    depends(request, ["HOME_SHARE_CREATED", "ssh_password"], scope="session")
    has_homes_share = False
    cmd = 'midclt call sharing.smb.reg_listshares'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if results['result'] is not True:
        return

    reg_shares = json.loads(results['output'].strip())
    for share in reg_shares:
        if share.casefold() == "homes".casefold():
            has_homes_share = True

    assert has_homes_share is True, results['output']


def test_017_convert_to_non_homes_share(request):
    depends(request, ["HOME_SHARE_CREATED"])
    results = PUT(f"/sharing/smb/id/{home_id}/",
                  {"home": False})
    assert results.status_code == 200, results.text


def test_018_verify_non_home_share_in_registry(request):
    """
    Unchecking "homes" should result in the "homes" share
    definition being removed and replaced with a new share
    name.
    """
    depends(request, ["HOME_SHARE_CREATED", "ssh_password"], scope="session")
    has_homes_share = False
    cmd = 'midclt call sharing.smb.reg_listshares'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if results['result'] is not True:
        return

    reg_shares = json.loads(results['output'].strip())
    for share in reg_shares:
        if share.casefold() == "HOME_CREATE".casefold():
            has_homes_share = True

    assert has_homes_share is True, results['output']


def test_019_convert_back_to_homes_share(request):
    depends(request, ["HOME_SHARE_CREATED"])
    results = PUT(f"/sharing/smb/id/{home_id}/",
                  {"home": True})
    assert results.status_code == 200, results.text


def test_020_verify_homeshare_in_registry(request):
    """
    One final test to confirm that changing back to
    a "homes" share reverts us to having a proper
    share definition for this special behavior.
    """
    depends(request, ["HOME_SHARE_CREATED", "ssh_password"], scope="session")
    has_homes_share = False
    cmd = 'midclt call sharing.smb.reg_listshares'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if results['result'] is not True:
        return

    reg_shares = json.loads(results['output'].strip())
    for share in reg_shares:
        if share.casefold() == "homes".casefold():
            has_homes_share = True

    assert has_homes_share is True, results['output']


def test_021_registry_has_single_entry(request):
    """
    By the point we've reached this test, the share
    definition has switched several times. This test
    verifies that we're properly removing the old share.
    """
    depends(request, ["HOME_SHARE_CREATED", "ssh_password"], scope="session")
    cmd = 'midclt call sharing.smb.reg_listshares'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    reg_shares = json.loads(results['output'].strip())
    assert len(reg_shares) == 1, results['output']


def test_022_registry_rebuild_homes(request):
    """
    Abusive test.
    In this test we run behind middleware's back and
    delete a our homes share from the registry, and then
    attempt to rebuild by registry sync method. This
    method is called (among other places) when the CIFS
    service reloads.
    """
    depends(request, ["HOME_SHARE_CREATED", "ssh_password"], scope="session")
    cmd = 'net conf delshare HOMES'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    payload = {"service": "cifs"}
    results = POST("/service/reload/", payload)
    assert results.status_code == 200, results.text

    has_homes_share = False
    cmd = 'midclt call sharing.smb.reg_listshares'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if results['result'] is not True:
        return

    reg_shares = json.loads(results['output'].strip())
    for share in reg_shares:
        if share.casefold() == "homes".casefold():
            has_homes_share = True

    assert has_homes_share is True, results['output']


def test_023_delete_home_share(request):
    depends(request, ["HOME_SHARE_CREATED"])
    results = DELETE(f"/sharing/smb/id/{home_id}")
    assert results.status_code == 200, results.text


def test_024_destroying_smb_dataset(request):
    depends(request, ["SMB_DATASET_CREATED"])
    results = DELETE(f"/pool/dataset/id/{DATASET_URL}/")
    assert results.status_code == 200, results.text
