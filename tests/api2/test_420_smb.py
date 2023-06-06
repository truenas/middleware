#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import contextlib
import pytest
import sys
import os
from pytest_dependency import depends
import json
import re
from datetime import datetime
from protocols import smb_connection
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST, cmd_test, send_file
from assets.REST.pool import dataset
from protocols import smb_connection, smb_share
from utils import create_dataset
from auto_config import ip, pool_name, password, user, hostname, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')

try:
    Reason = 'Windows host credential is missing in config.py'
    from config import WIN_HOST, WIN_USERNAME, WIN_PASSWORD
    windows_host_cred = pytest.mark.skipif(False, reason=Reason)
except ImportError:
    windows_host_cred = pytest.mark.skipif(True, reason=Reason)

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

@pytest.mark.dependency(name="smb_001")
def test_001_setting_auxilary_parameters_for_mount_smbfs(request):
    depends(request, ["shareuser"], scope="session")
    payload = {
        "enable_smb1": True,
        "guest": "shareuser"
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="create_dataset")
def test_002_creating_smb_dataset(request):
    depends(request, ["pool_04", "smb_001"], scope="session")
    payload = {
        "name": dataset,
        "share_type": "SMB",
        "acltype": "NFSV4"
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


def test_005_get_filesystem_stat_from_smb_path_and_verify_acl_is_true(request):
    depends(request, ["create_dataset"], scope="session")
    results = POST('/filesystem/stat/', SMB_PATH)
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is True, results.text


def test_006_starting_cifs_service_at_boot(request):
    depends(request, ["create_dataset"], scope="session")
    results = PUT("/service/id/cifs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_007_checking_to_see_if_clif_service_is_enabled_at_boot(request):
    depends(request, ["create_dataset"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is True, results.text


@pytest.mark.dependency(name="create_smb_share")
def test_008_creating_a_smb_share_path(request):
    depends(request, ["create_dataset"], scope="session")
    global payload, results, smb_id
    payload = {
        "comment": "My Test SMB Share",
        "path": SMB_PATH,
        "home": False,
        "name": SMB_NAME,
        "guestok": True,
        "purpose": "NO_PRESET",
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']


@pytest.mark.dependency(name="stating_cifs_service")
def test_009_starting_cifs_service(request):
    depends(request, ["create_smb_share"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


@pytest.mark.dependency(name="service_cifs_running")
def test_010_checking_to_see_if_nfs_service_is_running(request):
    depends(request, ["stating_cifs_service"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_011_verify_smbclient_127_0_0_1_connection(request):
    depends(request, ["service_cifs_running", "ssh_password"], scope="session")
    cmd = 'smbclient -NL //127.0.0.1'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'TestCifsSMB' in results['output'], results['output']
    assert 'My Test SMB Share' in results['output'], results['output']


@pytest.mark.parametrize('params', [
    ('SMB1', 'GUEST'),
    ('SMB2', 'GUEST'),
    ('SMB1', 'SHAREUSER'),
    ('SMB2', 'SHAREUSER')
])
def test_012_test_basic_smb_ops(request, params):
    depends(request, ["service_cifs_running"], scope="session")
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
    depends(request, ["service_cifs_running"], scope="session")
    payload = {
        "enable_smb1": False
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_019_change_sharing_smd_home_to_true_and_set_guestok_to_false(request):
    depends(request, ["service_cifs_running"], scope="session")
    payload = {
        'home': True,
        "guestok": False
    }
    results = PUT(f"/sharing/smb/id/{smb_id}", payload)
    assert results.status_code == 200, results.text


def test_020_verify_smbclient_127_0_0_1_nt_status_access_is_denied(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = 'smbclient -NL //127.0.0.1'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, results['output']
    assert 'NT_STATUS_ACCESS_DENIED' in results['output'], results['output']


def test_021_verify_smb_getparm_path_homes(request):
    depends(request, ["service_cifs_running", "ssh_password"], scope="session")
    cmd = 'midclt call smb.getparm path homes'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == f'{SMB_PATH}/%U'


def test_022_stoping_clif_service(request):
    depends(request, ["service_cifs_running"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_023_checking_if_cifs_is_stop(request):
    depends(request, ["service_cifs_running"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


def test_024_update_smb(request):
    depends(request, ["service_cifs_running"], scope="session")
    payload = {"syslog": False}
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_025_update_cifs_share(request):
    depends(request, ["service_cifs_running"], scope="session")
    results = PUT(f"/sharing/smb/id/{smb_id}/", {"home": False})
    assert results.status_code == 200, results.text


def test_026_starting_cifs_service(request):
    depends(request, ["service_cifs_running"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_027_checking_to_see_if_nfs_service_is_running(request):
    depends(request, ["service_cifs_running"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_034_change_timemachine_to_true(request):
    depends(request, ["service_cifs_running"], scope="session")
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
    depends(request, ["service_cifs_running"], scope="session")
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text
    assert results.json()['timemachine'] is True, results.text


@pytest.mark.parametrize('vfs_object', ["fruit", "streams_xattr"])
def test_036_verify_smb_getparm_vfs_objects_share(request, vfs_object):
    depends(request, ["service_cifs_running", "ssh_password"], scope="session")
    cmd = f'midclt call smb.getparm "vfs objects" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert vfs_object in results['output'], results['output']


def test_037_verify_smb_getparm_fruit_time_machine_is_yes(request):
    depends(request, ["service_cifs_running", "ssh_password"], scope="session")
    cmd = f'midclt call smb.getparm "fruit:time machine" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert bool(results['output'].strip()) is True, results['output']


def test_038_disable_time_machine(request):
    depends(request, ["service_cifs_running"], scope="session")
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
    depends(request, ["service_cifs_running"], scope="session")
    global vuid
    payload = {
        "recyclebin": True,
    }
    results = PUT(f"/sharing/smb/id/{smb_id}", payload)
    assert results.status_code == 200, results.text
    vuid = results.json()['vuid']


def test_040_verify_that_recyclebin_is_true(request):
    depends(request, ["service_cifs_running"], scope="session")
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text
    assert results.json()['recyclebin'] is True, results.text


@pytest.mark.parametrize('vfs_object', ["recycle"])
def test_041_verify_smb_getparm_vfs_objects_share(request, vfs_object):
    depends(request, ["service_cifs_running", "ssh_password"], scope="session")
    cmd = f'midclt call smb.getparm "vfs objects" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert vfs_object in results['output'], results['output']


def test_042_recyclebin_functional_test(request):
    with create_dataset(f'{dataset}/subds', {'share_type': 'SMB'}):
        with smb_connection(
            host=ip,
            share=SMB_NAME,
            username='shareuser',
            password='testing',
        ) as c:
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


@windows_host_cred
def test_047_create_a_dir_and_a_file_in_windows(request):
    depends(request, ["service_cifs_running", "ssh_password"], scope="session")
    cmd1 = 'mkdir testdir'
    results = SSH_TEST(cmd1, WIN_USERNAME, WIN_PASSWORD, WIN_HOST)
    assert results['result'] is True, results['output']
    cmd2 = r'echo some-text  > testdir\testfile.txt'
    results = SSH_TEST(cmd2, WIN_USERNAME, WIN_PASSWORD, WIN_HOST)
    assert results['result'] is True, results['output']
    cmd3 = r'dir testdir\testfile.txt'
    results3 = SSH_TEST(cmd3, WIN_USERNAME, WIN_PASSWORD, WIN_HOST)
    assert results3['result'] is True, results3['output']
    regex = re.compile(r"^.*testfile.*", re.MULTILINE)
    data_list = regex.findall(results3['output'])[0].split()
    global created_time, created_date
    created_time = data_list[1]
    created_date = data_list[0]


@windows_host_cred
def test_048_mount_the_smb_share_robocopy_testdir_to_the_share_windows_mount(request):
    depends(request, ["service_cifs_running", "ssh_password"], scope="session")
    # sleep 61 second to make sure that
    sleep(61)
    script = '@echo on\n'
    script += fr'net use X: \\{ip}\{SMB_NAME} /user:shareuser testing'
    script += '\n'
    script += r'robocopy testdir X:\testdir /COPY:DAT'
    script += '\n'
    script += r'dir X:\testdir'
    script += '\nnet use X: /delete\n'
    cmd_file = open('runtest.cmd', 'w')
    cmd_file.writelines(script)
    cmd_file.close()
    results = send_file(
        'runtest.cmd',
        'runtest.cmd',
        WIN_USERNAME,
        WIN_PASSWORD,
        WIN_HOST
    )
    assert results['result'] is True, results['output']
    cmd_results = SSH_TEST('runtest.cmd', WIN_USERNAME, WIN_PASSWORD, WIN_HOST)
    assert cmd_results['result'] is True, cmd_results['output']
    os.remove("runtest.cmd")
    cmd = 'del runtest.cmd'
    results = SSH_TEST(cmd, WIN_USERNAME, WIN_PASSWORD, WIN_HOST)
    assert results['result'] is True, results['output']
    regex = re.compile(r"^(?=.*testfile)(?!.*New).*", re.MULTILINE)
    data_list = regex.findall(cmd_results['output'])[0].split()
    global mounted_time, mounted_date
    mounted_time = data_list[1]
    mounted_date = data_list[0]


@windows_host_cred
def test_049_delete_the_test_dir_and_a_file_in_windows(request):
    depends(request, ["service_cifs_running"], scope="session")
    assert created_date == mounted_date
    assert created_time == mounted_time


@windows_host_cred
def test_050_verify_testfile_is_on_recycle_bin_in_the_active_directory_share(request):
    depends(request, ["service_cifs_running"], scope="session")
    """
    The server running this test, then Windows VM and TrueNAS VM should run
    on same timezone. If not this test will failed.
    """
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testdir/testfile.txt')
    assert results.status_code == 200, results.text
    atime = datetime.fromtimestamp(results.json()['atime'])
    mtime = datetime.fromtimestamp(results.json()['mtime'])
    assert created_date == atime.strftime('%m/%d/%Y')
    assert created_time == atime.strftime('%H:%M')
    assert created_date == mtime.strftime('%m/%d/%Y')
    assert created_time == mtime.strftime('%H:%M')


@windows_host_cred
def test_051_delete_the_test_dir_and_a_file_in_windows(request):
    depends(request, ["service_cifs_running", "ssh_password"], scope="session")
    cmd = 'rmdir /S /Q testdir'
    results = SSH_TEST(cmd, WIN_USERNAME, WIN_PASSWORD, WIN_HOST)
    assert results['result'] is True, results['output']


def test_052_get_smb_sharesec_id_and_set_smb_sharesec_share_acl(request):
    depends(request, ["service_cifs_running"], scope="session")
    global share_id, payload
    share_id = GET(f"/smb/sharesec/?share_name={SMB_NAME}").json()[0]['id']
    payload = {
        'share_acl': [
            {
                'ae_who_sid': 'S-1-5-32-544',
                'ae_perm': 'FULL',
                'ae_type': 'ALLOWED'
            }
        ]
    }
    results = PUT(f"/smb/sharesec/id/{share_id}/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('ae', ['ae_who_sid', 'ae_perm', 'ae_type'])
def test_053_verify_smb_sharesec_change_for(request, ae):
    depends(request, ["service_cifs_running"], scope="session")
    results = GET(f"/smb/sharesec/id/{share_id}/")
    assert results.status_code == 200, results.text
    ae_result = results.json()['share_acl'][0][ae]
    assert ae_result == payload['share_acl'][0][ae], results.text


def test_054_verify_midclt_call_smb_getparm_access_based_share_enum_is_false(request):
    depends(request, ["service_cifs_running", "ssh_password"], scope="session")
    cmd = f'midclt call smb.getparm "access based share enum" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == "False", results['output']


def test_055_delete_cifs_share(request):
    depends(request, ["service_cifs_running"], scope="session")
    results = DELETE(f"/sharing/smb/id/{smb_id}")
    assert results.status_code == 200, results.text


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
    depends(request, ["service_cifs_running"], scope="session")
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
    depends(request, ["SID_CHANGED", "ssh_password"], scope="session")
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
    groupmaps = json.loads(results['output'].strip())

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
    depends(request, ["SID_CHANGED", "ssh_password"], scope="session")
    payload = {
        "netbiosname": old_netbiosname,
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text
    sleep(5)

    cmd = "midclt call smb.groupmap_list"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    groupmaps = json.loads(results['output'].strip())

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


# Now stop the service
def test_060_disable_cifs_service_at_boot(request):
    depends(request, ["service_cifs_running"], scope="session")
    results = PUT("/service/id/cifs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_061_checking_to_see_if_clif_service_is_enabled_at_boot(request):
    depends(request, ["service_cifs_running"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is False, results.text


def test_062_stopping_cifs_service(request):
    depends(request, ["service_cifs_running"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_063_checking_if_cifs_is_stop(request):
    depends(request, ["service_cifs_running"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


# Check destroying a SMB dataset
def test_064_destroying_smb_dataset(request):
    depends(request, ["create_dataset"], scope="session")
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
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
