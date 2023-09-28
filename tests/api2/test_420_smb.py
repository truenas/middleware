#!/usr/bin/env python3

# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
from pytest_dependency import depends
import json
import uuid
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, SSH_TEST
from protocols import smb_connection
from utils import create_dataset
from auto_config import ip, pool_name, password, user, hostname
from middlewared.test.integration.assets.account import group
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset as make_dataset
from middlewared.test.integration.utils import client, ssh


MOUNTPOINT = f"/tmp/smb-cifs-{hostname}"
dataset = f"{pool_name}/smb-cifs"
dataset_url = dataset.replace('/', '%2F')
SMB_NAME = "TestCifsSMB"
SMB_PATH = "/mnt/" + dataset

guest_path_verification = {
    "user": "shareuser",
    "group": "root",
    "acl": True
}

root_path_verification = {
    "user": "root",
    "group": "root",
    "acl": False
}


@pytest.fixture(scope='module')
def initialize_for_smb_tests(request):
    with make_dataset('smb-cifs', data={'share_type': 'SMB'}) as ds:
        with smb_share(os.path.join('/mnt', ds), SMB_NAME, {
            'purpose': 'NO_PRESET',
            'guestok': True,
        }) as s:
            yield {'dataset': ds, 'share': s}


@pytest.mark.dependency(name="smb_initialized")
def test_001_enable_smb1(initialize_for_smb_tests):
    global smb_info
    global smb_id
    smb_info = initialize_for_smb_tests
    smb_id = smb_info['share']['id']

    with client() as c:
        c.call('smb.update', {"enable_smb1": True, 'guest': 'shareuser'})


@pytest.mark.parametrize('params', [
    ('SMB1', 'GUEST'),
    ('SMB2', 'GUEST'),
    ('SMB1', 'SHAREUSER'),
    ('SMB2', 'SHAREUSER')
])
def test_012_test_basic_smb_ops(request, params):
    depends(request, ["smb_initialized"], scope="session")
    proto, runas = params
    with smb_connection(
        host=ip,
        share=SMB_NAME,
        username=runas,
        password='testing',
        smb1=(proto == 'SMB1')
    ) as c:
        filename1 = f'testfile1_{proto.lower()}_{runas}.txt'
        filename2 = f'testfile2_{proto.lower()}_{runas}.txt'
        dirname = f'testdir_{proto.lower()}_{runas}.txt'

        fd = c.create_file(filename1, 'w')
        c.write(fd, b'foo')
        val = c.read(fd, 0, 3)
        c.close(fd, True)
        assert val == b'foo'

        c.mkdir(dirname)
        fd = c.create_file(f'{dirname}/{filename2}', 'w')
        c.write(fd, b'foo2')
        val = c.read(fd, 0, 4)
        c.close(fd, True)
        assert val == b'foo2'

        c.rmdir(dirname)

        # DELETE_ON_CLOSE flag was set prior to closing files
        # and so root directory should be empty
        assert c.ls('/') == []


def test_018_setting_enable_smb1_to_false(request):
    depends(request, ["smb_initialized"], scope="session")
    with client() as c:
        c.call('smb.update', {"enable_smb1": False})


def test_019_change_sharing_smd_home_to_true_and_set_guestok_to_false(request):
    depends(request, ["smb_initialized"], scope="session")
    with client() as c:
        c.call('sharing.smb.update', smb_id, {'home': True, "guestok": False})
        try:
            share_path = c.call('smb.getparm', 'path', 'homes')
            assert share_path == f'{SMB_PATH}/%U'
        finally:
            c.call('smb.update', smb_id, {'home': False})


def test_034_change_timemachine_to_true(request):
    depends(request, ["smb_initialized"], scope="session")
    with client() as c:
        c.call('smb.update', {'aapl_extensions': True})
        c.call('sharing.smb.update', smb_id, {'timemachine': True})
        try:
            share_info = c.call('sharing.smb.query', [['id', '=', smb_id]], {'get': True})
            assert share_info['timemachine'] is True

            enabled = c.call('smb.getparm', 'fruit:time machine', share_info['name'])
            assert enabled == 'True'

            vfs_obj = c.call('smb.getparm', 'vfs objects', share_info['name'])
            assert 'fruit' in vfs_obj
        finally:
            c.call('sharing.smb.update', smb_id, {'timemachine': False})
            c.call('smb.update', {'aapl_extensions': False})


@pytest.mark.dependency(name="SMB_RECYCLE_CONFIGURED")
def test_039_enable_recycle_bin(request):
    depends(request, ["smb_initialized"], scope="session")
    with client() as c:
        share_info = c.call('sharing.smb.update', smb_id, {'recyclebin': True})
        vfs_obj = c.call('smb.getparm', 'vfs objects', share_info['name'])
        assert 'recycle' in vfs_obj


def do_recycle_ops(c, has_subds=False):
    # Our recycle repository should be auto-created on connect.
    fd = c.create_file('testfile.txt', 'w')
    c.write(fd, b'foo')
    c.close(fd, True)

    # Above close op also deleted the file and so
    # we expect file to now exist in the user's .recycle directory
    fd = c.create_file('.recycle/shareuser/testfile.txt', 'r')
    val = c.read(fd, 0, 3)
    c.close(fd)
    assert val == b'foo'

    # re-open so that we can set DELETE_ON_CLOSE
    # this verifies that SMB client can purge file from recycle bin
    c.close(c.create_file('.recycle/shareuser/testfile.txt', 'w'), True)
    assert c.ls('.recycle/shareuser/') == []

    if not has_subds:
        return

    # nested datasets get their own recycle bin to preserve atomicity of
    # rename op.
    fd = c.create_file('subds/testfile2.txt', 'w')
    c.write(fd, b'boo')
    c.close(fd, True)

    fd = c.create_file('subds/.recycle/shareuser/testfile2.txt', 'r')
    val = c.read(fd, 0, 3)
    c.close(fd)
    assert val == b'boo'

    c.close(c.create_file('subds/.recycle/shareuser/testfile2.txt', 'w'), True)
    assert c.ls('subds/.recycle/shareuser/') == []


def test_042_recyclebin_functional_test(request):
    depends(request, ["SMB_RECYCLE_CONFIGURED"], scope="session")
    with create_dataset(f'{dataset}/subds', {'share_type': 'SMB'}):
        with smb_connection(
            host=ip,
            share=SMB_NAME,
            username='shareuser',
            password='testing',
        ) as c:
            do_recycle_ops(c, True)


@pytest.mark.parametrize('smb_config', [
    {'global': {'aapl_extensions': True}, 'share': {'aapl_name_mangling': True}},
    {'global': {'aapl_extensions': True}, 'share': {'aapl_name_mangling': False}},
    {'global': {'aapl_extensions': False}, 'share': {}},
])
def test_043_recyclebin_functional_test_subdir(request, smb_config):
    depends(request, ["SMB_RECYCLE_CONFIGURED"], scope="session")
    tmp_ds = f"{pool_name}/recycle_test"
    tmp_ds_path = f'/mnt/{tmp_ds}/subdir'
    tmp_share_name = 'recycle_test'

    results = PUT("/smb/", smb_config['global'])
    assert results.status_code == 200, results.text

    # basic tests of recyclebin operations
    with create_dataset(tmp_ds, {'share_type': 'SMB'}):
        results = SSH_TEST(f'mkdir {tmp_ds_path}', user, password, ip)
        assert results['result'] is True, f'out: {results["output"]}, err: {results["stderr"]}'

        with smb_share(tmp_ds_path, tmp_share_name, {
            'purpose': 'NO_PRESET',
            'recyclebin': True
        } | smb_config['share']):
            with smb_connection(
                host=ip,
                share=tmp_share_name,
                username='shareuser',
                password='testing',
            ) as c:
                do_recycle_ops(c)

    # more abusive test where first TCON op is opening file in subdir to delete
    with create_dataset(tmp_ds, {'share_type': 'SMB'}):
        ops = [
            f'mkdir {tmp_ds_path}',
            f'mkdir {tmp_ds_path}/subdir',
            f'touch {tmp_ds_path}/subdir/testfile',
            f'chown shareuser {tmp_ds_path}/subdir/testfile',
        ]
        results = SSH_TEST(';'.join(ops), user, password, ip)
        assert results['result'] is True, f'out: {results["output"]}, err: {results["stderr"]}'

        with smb_share(tmp_ds_path, tmp_share_name, {
            'purpose': 'NO_PRESET',
            'recyclebin': True
        } | smb_config['share']):
            with smb_connection(
                host=ip,
                share=tmp_share_name,
                username='shareuser',
                password='testing',
            ) as c:
                fd = c.create_file('subdir/testfile', 'w')
                c.write(fd, b'boo')
                c.close(fd, True)

                fd = c.create_file('.recycle/shareuser/subdir/testfile', 'r')
                val = c.read(fd, 0, 3)
                c.close(fd)
                assert val == b'boo'


@pytest.mark.dependency(name="SID_CHANGED")
def test_056_netbios_name_change_check_sid(request):
    """
    This test changes the netbios name of the server and then
    verifies that this results in the server's domain SID changing.
    The new SID is stored in a global variable so that we can
    perform additional tests to verify that SIDs are rewritten
    properly in group_mapping.tdb. old_netbiosname is stored so
    that we can reset configuration to what it was prior to the test.

    Test failure here shows that we failed to write our new SID
    to the configuration database.
    """
    depends(request, ["smb_initialized"], scope="session")
    global new_sid
    global old_netbiosname

    with client() as c:
        smb_config = c.call('smb.config')
        old_netbiosname = smb_config['netbiosname']
        old_sid = smb_config['cifs_SID']

        new_sid = c.call('smb.update', {'netbiosname': 'nb_new'})['cifs_SID']
        assert new_sid != old_sid


@pytest.mark.dependency(name="SID_TEST_GROUP")
def test_057_create_new_smb_group_for_sid_test(request):
    """
    Create testgroup and verify that groupmap entry generated
    with new SID.
    """
    def check_groupmap_for_entry(groupmaps, nt_name):
        for entry in groupmaps:
            if entry['nt_name'] == nt_name:
                return entry

        return None

    depends(request, ["SID_CHANGED"], scope="session")
    with client() as c:
        with group({'name': 'testsidgroup', 'smb': True}):
            groupmaps = c.call('smb.groupmap_list')

            test_entry = check_groupmap_for_entry(
                groupmaps['local'].values(),
                'testsidgroup'
            )
            assert test_entry is not None, groupmaps['local'].values()
            domain_sid = test_entry['sid'].rsplit("-", 1)[0]
            assert domain_sid == new_sid, groupmaps['local'].values()

            c.call('smb.update', {'netbiosname': old_netbiosname})

            groupmaps = c.call('smb.groupmap_list')
            test_entry = check_groupmap_for_entry(
                groupmaps['local'].values(),
                'testsidgroup'
            )

            assert test_entry is not None, groupmaps['local'].values()
            domain_sid = test_entry['sid'].rsplit("-", 1)[0]
            assert domain_sid != new_sid, groupmaps['local'].values()


AUDIT_FIELDS = [
    'aid', 'vers', 'time', 'addr', 'user', 'sess', 'svc',
    'svc_data', 'event', 'event_data', 'success'
]


def get_audit_entries(svc):
    cmd = "sqlite3 /audit/SMB.db '.mode line' "
    cmd += "\"SELECT * FROM audit_SMB_0_1, json_tree(audit_SMB_0_1.svc_data, '$.service') "
    cmd += f"where json_tree.value == '{svc}';\""
    entries = ssh(cmd).splitlines()
    output = []
    new_entry = None

    for entry in entries:
        if not entry:
            continue
        try:
            key, value = entry.strip().split("=", 1)
        except Exception:
            continue

        key = key.strip()
        value = value.strip()
        if key not in AUDIT_FIELDS:
            continue

        if key == 'aid':
            if new_entry:
                output.append(new_entry)

            new_entry = {}

        new_entry[key] = value

    if new_entry:
        output.append(new_entry)

    return output


def validate_vers(vers, expected_major, expected_minor):
    assert 'major' in vers, str(vers)
    assert 'minor' in vers, str(vers)
    assert vers['major'] == expected_major
    assert vers['minor'] == expected_minor


def validate_svc_data(msg, svc):
    assert 'svc_data' in msg, str(msg)
    try:
        svc_data = json.loads(msg['svc_data'])
    except json.decoder.JSONDecodeError as e:
        raise AssertionError(f'svc_data contains invalid JSON: {msg["svc_data"]}: {e}')

    for key in ['vers', 'service', 'session_id', 'tcon_id']:
        assert key in svc_data, str(svc_data)

    assert svc_data['service'] == svc

    assert isinstance(svc_data['session_id'], str)
    assert svc_data['session_id'].isdigit()

    assert isinstance(svc_data['tcon_id'], str)
    assert svc_data['tcon_id'].isdigit()


def validate_audit_op(msg, svc):
    for key in AUDIT_FIELDS:
        assert key in msg, str(msg)

    validate_svc_data(msg, svc)
    try:
        aid_guid = uuid.UUID(msg['aid'])
    except ValueError:
        raise AssertionError(f'{msg["aid"]}: malformed UUID')

    assert str(aid_guid) == msg['aid']

    try:
        sess_guid = uuid.UUID(msg['sess'])
    except ValueError:
        raise AssertionError(f'{msg["sess"]}: malformed UUID')

    assert str(sess_guid) == msg['sess']


def do_audit_ops(svc):
    with smb_connection(
        host=ip,
        share=svc,
        username='shareuser',
        password='testing',
    ) as c:
        fd = c.create_file('testfile.txt', 'w')
        for i in range(0, 3):
            c.write(fd, b'foo')
            c.read(fd, 0, 3)
        c.close(fd, True)

    sleep(10)
    return get_audit_entries(svc)


def test_060_audit_log(request):
    def get_event(event_list, ev_type):
        for e in event_list:
            if e['event'] == ev_type:
                return e

        return None

    depends(request, ["smb_initialized"], scope="session")
    with make_dataset('smb-audit', data={'share_type': 'SMB'}) as ds:
        with smb_share(os.path.join('/mnt', ds), 'SMB_AUDIT', {
            'purpose': 'NO_PRESET',
            'guestok': True,
            'audit': {'enable': True}
        }) as s:
            events = do_audit_ops(s['name'])
            assert len(events) > 0

            for ev_type in ['CONNECT', 'DISCONNECT', 'CREATE', 'CLOSE', 'READ', 'WRITE']:
                assert get_event(events, ev_type) is not None, str(events)

            for event in events:
                validate_audit_op(event, s['name'])

            results = PUT(f"/sharing/smb/id/{s['id']}/", {'audit': {'ignore_list': ['builtin_users']}})
            assert results.status_code == 200, results.text
            new_data = results.json()

            assert new_data['audit']['enable'], str(new_data['audit'])
            assert new_data['audit']['ignore_list'] == ['builtin_users'], str(new_data['audit'])

            # Verify that being member of group in ignore list is sufficient to avoid new messages
            assert len(do_audit_ops(s['name'])) == len(events)

            results = PUT(f"/sharing/smb/id/{s['id']}/", {'audit': {'watch_list': ['builtin_users']}})
            assert results.status_code == 200, results.text
            new_data = results.json()

            assert new_data['audit']['enable'], str(new_data['audit'])
            assert new_data['audit']['ignore_list'] == ['builtin_users'], str(new_data['audit'])
            assert new_data['audit']['watch_list'] == ['builtin_users'], str(new_data['audit'])

            # Verify that watch_list takes precedence
            new_events = do_audit_ops(s['name'])
            assert len(new_events) > len(events)

            results = PUT(f"/sharing/smb/id/{s['id']}/", {'audit': {'enable': False}})
            assert results.status_code == 200, results.text
            new_data = results.json()

            assert new_data['audit']['enable'] is False, str(new_data['audit'])
            assert new_data['audit']['ignore_list'] == ['builtin_users'], str(new_data['audit'])
            assert new_data['audit']['watch_list'] == ['builtin_users'], str(new_data['audit'])

            # Verify that disabling audit prevents new messages from being written
            assert len(do_audit_ops(s['name'])) == len(new_events)


@pytest.mark.parametrize('torture_test', [
    'local.binding',
    'local.ntlmssp',
    'local.smbencrypt',
    'local.messaging',
    'local.irpc',
    'local.strlist',
    'local.file',
    'local.str',
    'local.time',
    'local.datablob',
    'local.binsearch',
    'local.asn1',
    'local.anonymous_shared',
    'local.strv',
    'local.strv_util',
    'local.util',
    'local.idtree',
    'local.dlinklist',
    'local.genrand',
    'local.iconv',
    'local.socket',
    'local.pac',
    'local.share',
    'local.loadparm',
    'local.charset',
    'local.convert_string',
    'local.string_case_handle',
    'local.tevent_req',
    'local.util_str_escape',
    'local.talloc',
    'local.replace',
    'local.crypto.md4'
])
def test_065_local_torture(request, torture_test):
    results = SSH_TEST(f'smbtorture //127.0.0.1 {torture_test}', user, password, ip)
    assert results['result'] is True, results['output']
