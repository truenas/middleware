#!/usr/bin/env python3

# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
from pytest_dependency import depends
import json
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST
from protocols import smb_connection
from utils import create_dataset
from auto_config import ip, pool_name, password, user, hostname, dev_test
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset as make_dataset
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')

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

    results = PUT("/smb/", {"enable_smb1": True, 'guest': 'shareuser'})
    assert results.status_code == 200, results.text


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
    payload = {
        "enable_smb1": False
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_019_change_sharing_smd_home_to_true_and_set_guestok_to_false(request):
    depends(request, ["smb_initialized"], scope="session")
    payload = {
        'home': True,
        "guestok": False
    }
    results = PUT(f"/sharing/smb/id/{smb_id}", payload)
    assert results.status_code == 200, results.text


def test_021_verify_smb_getparm_path_homes(request):
    depends(request, ["smb_initialized"], scope="session")
    cmd = 'midclt call smb.getparm path homes'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['stdout'].strip() == f'{SMB_PATH}/%U'


def test_025_disable_homes(request):
    depends(request, ["smb_initialized"], scope="session")
    results = PUT(f"/sharing/smb/id/{smb_id}/", {"home": False})
    assert results.status_code == 200, results.text


def test_034_change_timemachine_to_true(request):
    depends(request, ["smb_initialized"], scope="session")
    payload = {
        "aapl_extensions": True
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text

    global vuid
    payload = {
        'timemachine': True,
    }
    results = PUT(f"/sharing/smb/id/{smb_id}/", payload)
    assert results.status_code == 200, results.text
    vuid = results.json()['vuid']


def test_035_verify_that_timemachine_is_true(request):
    depends(request, ["smb_initialized"], scope="session")
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text
    assert results.json()['timemachine'] is True, results.text


@pytest.mark.parametrize('vfs_object', ["fruit", "streams_xattr"])
def test_036_verify_smb_getparm_vfs_objects_share(request, vfs_object):
    depends(request, ["smb_initialized"], scope="session")
    cmd = f'midclt call smb.getparm "vfs objects" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert vfs_object in results['output'], results['output']


def test_037_verify_smb_getparm_fruit_time_machine_is_yes(request):
    depends(request, ["smb_initialized"], scope="session")
    cmd = f'midclt call smb.getparm "fruit:time machine" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert bool(results['stdout'].strip()) is True, results['output']


def test_038_disable_time_machine(request):
    depends(request, ["smb_initialized"], scope="session")
    payload = {
        'timemachine': False,
    }
    results = PUT(f"/sharing/smb/id/{smb_id}/", payload)
    assert results.status_code == 200, results.text

    payload = {
        "aapl_extensions": False
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_039_change_recyclebin_to_true(request):
    depends(request, ["smb_initialized"], scope="session")
    global vuid
    payload = {
        "recyclebin": True,
    }
    results = PUT(f"/sharing/smb/id/{smb_id}", payload)
    assert results.status_code == 200, results.text
    vuid = results.json()['vuid']


def test_040_verify_that_recyclebin_is_true(request):
    depends(request, ["smb_initialized"], scope="session")
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text
    assert results.json()['recyclebin'] is True, results.text


@pytest.mark.parametrize('vfs_object', ["recycle"])
def test_041_verify_smb_getparm_vfs_objects_share(request, vfs_object):
    depends(request, ["smb_initialized"], scope="session")
    cmd = f'midclt call smb.getparm "vfs objects" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert vfs_object in results['output'], results['output']


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
    depends(request, ["smb_initialized"], scope="session")
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
        } | smb_config['share']) as s:
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
        } | smb_config['share']) as s:
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

    results = GET("/smb/")
    assert results.status_code == 200, results.text
    old_netbiosname = results.json()["netbiosname"]
    old_sid = results.json()["cifs_SID"]

    payload = {
        "netbiosname": "nb_new",
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text
    new_sid_resp = results.json()["cifs_SID"]
    assert old_sid != new_sid_resp, results.text
    sleep(5)

    results = GET("/smb/")
    assert results.status_code == 200, results.text
    new_sid = results.json()["cifs_SID"]
    assert new_sid != old_sid, results.text


@pytest.mark.dependency(name="SID_TEST_GROUP")
def test_057_create_new_smb_group_for_sid_test(request):
    """
    Create testgroup and verify that groupmap entry generated
    with new SID.
    """
    depends(request, ["SID_CHANGED"], scope="session")
    global group_id
    payload = {
        "name": "testsidgroup",
        "smb": True,
    }
    results = POST("/group/", payload)
    assert results.status_code == 200, results.text
    group_id = results.json()
    sleep(5)

    cmd = "midclt call smb.groupmap_list"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    groupmaps = json.loads(results['stdout'].strip())

    test_entry = None
    for entry in groupmaps['local'].values():
        if entry['nt_name'] == 'testsidgroup':
            test_entry = entry
            break

    assert test_entry is not None, groupmaps['local'].values()
    domain_sid = test_entry['sid'].rsplit("-", 1)[0]
    assert domain_sid == new_sid, groupmaps['local'].values()


def test_058_change_netbios_name_and_check_groupmap(request):
    """
    Verify that changes to netbios name result in groupmap sid
    changes.
    """
    depends(request, ["SID_CHANGED"], scope="session")
    payload = {
        "netbiosname": old_netbiosname,
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text
    sleep(5)

    cmd = "midclt call smb.groupmap_list"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    groupmaps = json.loads(results['stdout'].strip())

    test_entry = None
    for entry in groupmaps['local'].values():
        if entry['nt_name'] == 'testsidgroup':
            test_entry = entry
            break

    assert test_entry is not None, groupmaps['local'].values()
    domain_sid = test_entry['sid'].rsplit("-", 1)[0]
    assert domain_sid != new_sid, groupmaps['local'].values()


def test_059_delete_smb_group(request):
    depends(request, ["SID_TEST_GROUP"])
    results = DELETE(f"/group/id/{group_id}/")
    assert results.status_code == 200, results.text


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
    'local.event',
    'local.tevent_req',
    'local.util_str_escape',
    'local.talloc',
    'local.replace',
    'local.crypto.md4'
])
def test_065_local_torture(request, torture_test):
    results = SSH_TEST(f'smbtorture //127.0.0.1 {torture_test}', user, password, ip)
    assert results['result'] is True, results['output']
