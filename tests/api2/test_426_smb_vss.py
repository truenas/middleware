from subprocess import run
from time import sleep

import pytest
from pytest_dependency import depends

# DO NOT change the order of these imports
# or the ntstatus import will fail
from protocols import SMB
from samba import ntstatus

from auto_config import pool_name, user, password
from functions import SSH_TEST
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import truenas_server


dataset = f"{pool_name}/smb-vss"
dataset_nested = f"{dataset}/sub1"

SMB_NAME = "SMBVSS"
smb_path = "/mnt/" + dataset

SMB_USER = "smbshadowuser"
SMB_PWD = "smb1234"

to_check = [
    'testfile1',
    f'{SMB_USER}/testfile2',
    'sub1/testfile3'
]

snapshots = {
    'snapshot1': {'gmt_string': '', 'offset': 18},
    'snapshot2': {'gmt_string': '', 'offset': 36},
    'snapshot3': {'gmt_string': '', 'offset': 54},
}


def check_previous_version_exists(path, home=False):
    ip = truenas_server.ip
    cmd = [
        'smbclient',
        f'//{ip}/{SMB_NAME if not home else SMB_USER}',
        '-U', f'{SMB_USER}%{SMB_PWD}',
        '-c' f'open {path}'
    ]
    cli_open = run(cmd, capture_output=True)
    if cli_open.returncode != 0:
        return (
            ntstatus.NT_STATUS_FAIL_CHECK,
            'NT_STATUS_FAIL_CHECK',
            cli_open.stderr.decode()
        )

    cli_output = cli_open.stdout.decode().strip()
    if 'NT_STATUS_' not in cli_output:
        return (0, 'NT_STATUS_OK', cli_output)

    cli_output = cli_output.rsplit(' ', 1)

    return (
        ntstatus.__getattribute__(cli_output[1]),
        cli_output[1],
        cli_output[0]
    )


"""
def check_previous_version_contents(path, contents, offset):
    cmd = [
        'smbclient',
        f'//{ip}/{SMB_NAME}',
        '-U', f'{SMB_USER}%{SMB_PWD}',
        '-c' f'prompt OFF; mget {path}'
    ]
    cli_get = run(cmd, capture_output=True)
    if cli_get.returncode != 0:
        return (
            ntstatus.NT_STATUS_FAIL_CHECK,
            'NT_STATUS_FAIL_CHECK',
            cli_open.stderr.decode()
        )

    cli_output = cli_get.stdout.decode().strip()
    if 'NT_STATUS_' in cli_output:
        cli_output = cli_output.rsplit(' ', 1)
        return (
            ntstatus.__getattribute__(cli_output[1]),
            cli_output[0]
        )

    with open(path[25:], "rb") as f:
        bytes = f.read()

    to_check = bytes[offset:]
    assert len(to_check) == 9, f'path: {path}, contents: {to_check.decode()}'
    os.unlink(path[25:])
    assert to_check.decode() == contents, path
    return (0, )
"""


@pytest.mark.parametrize('ds', [dataset, dataset_nested])
@pytest.mark.dependency(name="VSS_DATASET_CREATED")
def test_001_creating_smb_dataset(request, ds):
    assert call("pool.dataset.create", {"name": ds, "share_type": "SMB"})
    assert call("pool.snapshot.create", {"dataset": ds, "name": "init"})


@pytest.mark.dependency(name="VSS_USER_CREATED")
def test_002_creating_shareuser_to_test_acls(request):
    depends(request, ['VSS_DATASET_CREATED'])

    global vssuser_id
    global next_uid
    next_uid = call('user.get_next_uid')
    vssuser_id = call("user.create", {
        "username": SMB_USER,
        "full_name": "SMB User",
        "group_create": True,
        "password": SMB_PWD,
        "uid": next_uid,
    })['id']


def test_003_changing_dataset_owner(request):
    depends(request, ["VSS_USER_CREATED"])
    call(
        "filesystem.chown",
        {
            'path': smb_path,
            'uid': next_uid,
            'options': {'recursive': True, 'traverse': True},
        },
        job=True
    )


@pytest.mark.dependency(name="VSS_SHARE_CREATED")
def test_004_creating_a_smb_share_path(request):
    depends(request, ["VSS_DATASET_CREATED"], scope="session")
    global payload, results, smb_id
    smb_id = call("sharing.smb.create", {
        "comment": "SMB VSS Testing Share",
        "path": smb_path,
        "name": SMB_NAME,
        "purpose": "LEGACY_SHARE",
    })['id']
    cmd = f'mkdir {smb_path}/{SMB_USER}; zpool sync; net cache flush'
    results = SSH_TEST(cmd, user, password)
    assert results['result'] is True, {"cmd": cmd, "res": results['output']}


@pytest.mark.dependency(name="VSS_SMB_SERVICE_STARTED")
def test_005_starting_cifs_service(request):
    depends(request, ["VSS_SHARE_CREATED"])
    assert call("service.control", "START", "cifs", job=True)


@pytest.mark.dependency(name="VSS_SMB1_ENABLED")
def test_006_enable_smb1(request):
    depends(request, ["VSS_SHARE_CREATED"])
    assert call("smb.update", {"enable_smb1": True})


@pytest.mark.dependency(name="SHARE_HAS_SHADOW_COPIES")
@pytest.mark.parametrize('proto', ["SMB1", "SMB2"])
def test_007_check_shadow_copies(request, proto):
    """
    This is very basic validation of presence of snapshot
    over SMB1 and SMB2/3.
    """
    depends(request, ["VSS_USER_CREATED"])
    c = SMB()
    snaps = c.get_shadow_copies(
        share=SMB_NAME,
        username=SMB_USER,
        password=SMB_PWD,
        smb1=(proto == "SMB1")
    )
    assert len(snaps) == 1, snaps


@pytest.mark.dependency(name="VSS_TESTFILES_CREATED")
@pytest.mark.parametrize('payload', [
    'snapshot1', 'snapshot2', 'snapshot3'
])
def test_008_set_up_testfiles(request, payload):
    depends(request, ["SHARE_HAS_SHADOW_COPIES"])
    i = int(payload[-1])
    offset = i * 2 * len(payload)
    c = SMB()
    c.connect(share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=False)

    for f in to_check:
        fd = c.create_file(f, "w")
        c.write(fd, payload.encode(), offset)
        c.close(fd)

        fd = c.create_file(f'{f}:smb2_stream', 'w')
        c.write(fd, payload.encode(), offset)
        c.close(fd)

    sleep(5)
    assert call("pool.snapshot.create", {
        "dataset": dataset,
        "name": payload,
        "recursive": True,
    })


@pytest.mark.parametrize('proto', ["SMB1", "SMB2"])
def test_009_check_shadow_copies_count_after_setup(request, proto):
    """
    This is very basic validation of presence of snapshot
    over SMB1 and SMB2/3.
    """
    depends(request, ["VSS_USER_CREATED"])
    c = SMB()
    snaps = c.get_shadow_copies(
        share=SMB_NAME,
        username=SMB_USER,
        password=SMB_PWD,
        smb1=(proto == "SMB1")
    )
    assert len(snaps) == 4, snaps
    snaps.sort()
    for idx, gmt in enumerate(snaps[1:]):
        snapshots[f'snapshot{idx + 1}']['gmt_string'] = gmt


@pytest.mark.dependency(name="VSS_TESTFILES_VALIDATED")
@pytest.mark.parametrize('zfs, gmt_data', snapshots.items())
def test_010_check_previous_versions_of_testfiles(request, zfs, gmt_data):
    """
    This test verifies that previous versions of files can be opened successfully
    in the following situations:
    1) root of share
    2) subdirectory in share
    3) child dataset in share

    in (1) - (3) above, ability to open alternate data streams is also verified.
    """
    depends(request, ["VSS_TESTFILES_CREATED"])

    vers = gmt_data['gmt_string']
    for f in to_check:
        the_file = f'{vers}/{f}'
        err, errstr, msg = check_previous_version_exists(the_file)
        assert err == 0, f'{the_file}: {errstr} - {msg}'

        """
        # further development of libsmb / smbclient required for this test
        # best bet is to add a kwarg to py-libsmb create to allow openinging
        # previous version of file.
        err, msg = check_previous_version_contents(the_file, zfs, gmt_data['offset'])
        assert err == 0, f'{the_file}: {msg}'
        """
        err, errstr, msg = check_previous_version_exists(f'{the_file}:smb2_stream')
        assert err == 0, f'{the_file}:smb2_stream: {errstr} - {msg}'


def test_011_convert_to_home_share(request):
    depends(request, ["VSS_TESTFILES_VALIDATED"])
    assert call("sharing.smb.update", smb_id, {
        "purpose": "LEGACY_SHARE",
        "options": {"home": True}
    })


@pytest.mark.parametrize('zfs, gmt_data', snapshots.items())
def test_012_check_previous_versions_of_testfiles_home_share(request, zfs, gmt_data):
    """
    This test verifies that previous versions of files can be opened successfully
    in the following situations:
    1) root of share
    2) subdirectory in share
    3) child dataset in share

    in (1) - (3) above, ability to open alternate data streams is also verified.
    Differs from previous test in that this one covers a "home" share, which is
    of a directory inside a ZFS dataset, which means that internally samba cwd
    has to change to path outside of share root.
    """
    depends(request, ["VSS_TESTFILES_VALIDATED"])
    the_file = f'{gmt_data["gmt_string"]}/testfile2'
    err, errstr, msg = check_previous_version_exists(the_file, True)
    assert err == 0, f'{the_file}: {errstr} - {msg}'


def test_050_delete_smb_user(request):
    depends(request, ["VSS_USER_CREATED"])
    call("user.delete", vssuser_id, {"delete_group": True})
    call("sharing.smb.delete", smb_id)


def test_051_disable_smb1(request):
    depends(request, ["VSS_SMB1_ENABLED"])
    assert call("smb.update", {"enable_smb1": False, "aapl_extensions": False})


def test_052_stopping_smb_service(request):
    depends(request, ["VSS_SMB_SERVICE_STARTED"])
    assert call("service.control", "STOP", "cifs", job=True)
    sleep(1)


def test_053_checking_if_smb_is_stoped(request):
    depends(request, ["VSS_SMB_SERVICE_STARTED"])
    assert call(
        "service.query",
        [["service", "=", "cifs"]],
        {"get": True},
    )["state"] == "STOPPED"


def test_054_destroying_smb_dataset(request):
    depends(request, ["VSS_DATASET_CREATED"])
    call("pool.dataset.delete", dataset, {'recursive': True})
