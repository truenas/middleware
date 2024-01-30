#!/usr/bin/env python3

import pytest
import sys
import os
import enum
import secrets
import string
from base64 import b64decode, b64encode
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, SSH_TEST
from auto_config import (
    ip,
    user,
    password,
)
from middlewared.test.integration.assets.account import user as create_user
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh
from pytest_dependency import depends
from protocols import SMB, smb_connection
from samba import ntstatus
from samba import NTSTATUSError


SMB_NAME = "SMBPROTO"
SMB_USER = "smbuser"
SMB_PWD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))
TEST_DATA = {}
pytestmark = pytest.mark.smb


class DOSmode(enum.Enum):
    READONLY = 1
    HIDDEN = 2
    SYSTEM = 4
    ARCHIVE = 32


netatalk_metadata = """
AAUWBwACAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAEAAAAmgAAAAAAAAAIAAABYgAAABAAAAAJAAAA
egAAACAAAAAOAAABcgAAAASAREVWAAABdgAAAAiASU5PAAABfgAAAAiAU1lOAAABhgAAAAiAU1Z+
AAABjgAAAARQTEFQbHRhcAQQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAIbmGsyG5hrOAAAAAKEvSOAAAAAAAAAAAAAAAAAcBAAAAAAAA9xS5YAAAAAAZ
AAAA
"""

parsed_meta = """
QUZQAAAAAQAAAAAAgAAAAFBMQVBsdGFwBBAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAA
"""

apple_kmdlabel = """
8oBNzAaTG04NeBVAT078KCEjrzPrwPTUuZ4MXK1qVRDlBqLATmFSDFO2hXrS5VWsrg1DoZqeX6kF
zDEInIzw2XrZkI9lY3jvMAGXu76QvwrpRGv1G3Ehj+0=
"""

apple_kmditemusertags = """
YnBsaXN0MDCgCAAAAAAAAAEBAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAJ
"""

AFPXattr = {
    "org.netatalk.Metadata": {
        "smbname": "AFP_AfpInfo",
        "text": netatalk_metadata,
        "bytes": b64decode(netatalk_metadata),
        "smb_text": parsed_meta,
        "smb_bytes": b64decode(parsed_meta)
    },
    "com.apple.metadata:_kMDItemUserTags": {
        "smbname": "com.apple.metadata_kMDItemUserTags",
        "text": apple_kmditemusertags,
        "bytes": b64decode(apple_kmditemusertags)
    },
    "com.apple.metadata:kMDLabel_anemgxoe73iplck2hfuumqxdbu": {
        "smbname": "com.apple.metadatakMDLabel_anemgxoe73iplck2hfuumqxdbu",
        "text": apple_kmdlabel,
        "bytes": b64decode(apple_kmdlabel)
    },
}


@pytest.fixture(scope='module')
def initialize_for_smb_tests(request):
    with dataset('smb-proto', data={'share_type': 'SMB'}) as ds:
        with create_user({
            'username': SMB_USER,
            'full_name': SMB_USER,
            'group_create': True,
            'password': SMB_PWD
        }) as u:
            with smb_share(os.path.join('/mnt', ds), SMB_NAME, {
                'auxsmbconf': 'zfs_core:base_user_quota = 1G'
            }) as s:
                try:
                    call('service.start', 'cifs')
                    yield {'dataset': ds, 'share': s, 'user': u}
                finally:
                    call('smb.update', {
                        'enable_smb1': False,
                        'aapl_extensions': False
                    })
                    call('service.stop', 'cifs')


@pytest.mark.dependency(name="SMB_SHARE_CREATED")
def test_001_initialize_smb_servce(initialize_for_smb_tests):
    TEST_DATA.update(initialize_for_smb_tests)


def test_002_check_client_count(request):
    depends(request, ["SMB_SHARE_CREATED"])
    with smb_connection(
        host=ip,
        share=SMB_NAME,
        username=SMB_USER,
        password=SMB_PWD,
        smb1=False
    ) as c:
        assert call("smb.client_count") == 1


@pytest.mark.dependency(name="SHARE_IS_WRITABLE")
def test_009_share_is_writable(request):
    """
    This test creates creates an empty file, sets "delete on close" flag, then
    closes it. NTStatusError should be raised containing failure details
    if we are for some reason unable to access the share.

    This test will fail if smb.conf / smb4.conf does not exist on client / server running test.
    """
    depends(request, ["SMB_SHARE_CREATED"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=False)
    fd = c.create_file("testfile", "w")
    c.close(fd, True)
    c.disconnect()


@pytest.mark.parametrize('dm', DOSmode)
def test_010_check_dosmode_create(request, dm):
    """
    This tests the setting of different DOS attributes through SMB2 Create.
    after setting
    """
    depends(request, ["SHARE_IS_WRITABLE"])
    if dm.value > DOSmode.SYSTEM.value:
        return

    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=False)
    if dm == DOSmode.READONLY:
        c.create_file(dm.name, "w", "r")
    elif dm == DOSmode.HIDDEN:
        c.create_file(dm.name, "w", "h")
    elif dm == DOSmode.SYSTEM:
        c.create_file(dm.name, "w", "s")
    dir_listing = c.ls("/")
    for f in dir_listing:
        if f['name'] != dm.name:
            continue
        # Archive is automatically set by kernel
        to_check = f['attrib'] & ~DOSmode.ARCHIVE.value
        c.disconnect()
        assert (to_check & dm.value) != 0, f


def test_011_check_dos_ro_cred_handling(request):
    """
    This test creates a file with readonly attribute set, then
    uses the open fd to write data to the file.
    """
    depends(request, ["SHARE_IS_WRITABLE"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=False)
    fd = c.create_file("RO_TEST", "w", "r")
    c.write(fd, b"TESTING123\n")
    c.disconnect()


@pytest.mark.dependency(name="SMB1_ENABLED")
def test_050_enable_smb1(request):
    depends(request, ["SMB_SHARE_CREATED"])
    payload = {
        "enable_smb1": True,
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="SHARE_IS_WRITABLE_SMB1")
def test_051_share_is_writable_smb1(request):
    """
    This test creates creates an empty file, sets "delete on close" flag, then
    closes it. NTStatusError should be raised containing failure details
    if we are for some reason unable to access the share.

    This test will fail if client min protocol != NT1 in smb.conf of SMB client.
    Sample smb.conf entry:

    [global]
    client min protocol = nt1
    """
    depends(request, ["SMB_SHARE_CREATED"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=True)
    fd = c.create_file("testfile", "w")
    c.close(fd, True)
    c.disconnect()


@pytest.mark.parametrize('dm', DOSmode)
def test_052_check_dosmode_create_smb1(request, dm):
    """
    This tests the setting of different DOS attributes through SMB1 create.
    after setting
    """
    depends(request, ["SHARE_IS_WRITABLE"])
    if dm.value > DOSmode.SYSTEM.value:
        return

    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=True)
    if dm == DOSmode.READONLY:
        c.create_file(f'{dm.name}_smb1', "w", "r")
    elif dm == DOSmode.HIDDEN:
        c.create_file(f'{dm.name}_smb1', "w", "h")
    elif dm == DOSmode.SYSTEM:
        c.create_file(f'{dm.name}_smb1', "w", "s")
    dir_listing = c.ls("/")
    for f in dir_listing:
        if f['name'] != f'{dm.name}_smb1':
            continue
        # Archive is automatically set by kernel
        to_check = f['attrib'] & ~DOSmode.ARCHIVE.value
        c.disconnect()
        assert (to_check & dm.value) != 0, f


@pytest.mark.dependency(name="STREAM_TESTFILE_CREATED")
def test_060_create_base_file_for_streams_tests(request):
    """
    Create the base file that we will use for further stream tests.
    """
    depends(request, ["SMB_SHARE_CREATED"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=True)
    fd = c.create_file("streamstestfile", "w")
    c.close(fd)
    c.mkdir("streamstestdir")
    c.disconnect()


@pytest.mark.dependency(name="STREAM_WRITTEN_SMB2")
def test_061_create_and_write_stream_smb2(request):
    """
    Create our initial stream and write to it over SMB2/3 protocol.
    Start with offset 0.
    """
    depends(request, ["STREAM_TESTFILE_CREATED"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=False)
    fd = c.create_file("streamstestfile:smb2_stream", "w")
    c.write(fd, b'test1', 0)
    c.close(fd)

    fd2 = c.create_file("streamstestdir:smb2_stream", "w")
    c.write(fd2, b'test2', 0)
    c.close(fd2)

    fd3 = c.create_file("streamstestfile:smb2_stream", "w")
    contents = c.read(fd3, 0, 5)
    c.close(fd3)

    fd4 = c.create_file("streamstestdir:smb2_stream", "w")
    contents2 = c.read(fd4, 0, 5)
    c.close(fd4)

    c.rmdir("streamstestdir")
    c.disconnect()
    assert (contents.decode() == "test1")
    assert (contents2.decode() == "test2")


@pytest.mark.dependency(name="LARGE_STREAM_WRITTEN_SMB2")
def test_062_write_stream_large_offset_smb2(request):
    """
    Append to our existing stream over SMB2/3 protocol. Specify an offset that will
    cause resuling xattr to exceed 64KiB default xattr size limit in Linux.
    """
    depends(request, ["STREAM_TESTFILE_CREATED"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=False)
    fd = c.create_file("streamstestfile:smb2_stream", "w")
    c.write(fd, b'test2', 131072)
    c.close(fd)

    fd2 = c.create_file("streamstestfile:smb2_stream", "w")
    contents = c.read(fd2, 131072, 5)
    c.close(fd2)
    c.disconnect()
    assert (contents.decode() == "test2")


def test_063_stream_delete_on_close_smb2(request):
    """
    Set delete_on_close on alternate datastream over SMB2/3 protocol, close, then verify
    stream was deleted.

    TODO: I have open MR to expand samba python bindings to support stream enumeration.
    Verifcation of stream deletion will have to be added once this is merged.
    """
    depends(request, ["STREAM_WRITTEN_SMB2", "LARGE_STREAM_WRITTEN_SMB2"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=False)
    fd = c.create_file("streamstestfile:smb2_stream", "w")
    c.close(fd, True)

    c.disconnect()


@pytest.mark.dependency(name="STREAM_WRITTEN_SMB1")
def test_065_create_and_write_stream_smb1(request):
    """
    Create our initial stream and write to it over SMB1 protocol.
    Start with offset 0.
    """
    depends(request, ["STREAM_TESTFILE_CREATED"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=True)
    fd = c.create_file("streamstestfile:smb1_stream", "w")
    c.write(fd, b'test1', 0)
    c.close(fd)

    fd2 = c.create_file("streamstestfile:smb1_stream", "w")
    contents = c.read(fd2, 0, 5)
    c.close(fd2)
    c.disconnect()
    assert (contents.decode() == "test1")


@pytest.mark.dependency(name="LARGE_STREAM_WRITTEN_SMB1")
def test_066_write_stream_large_offset_smb1(request):
    """
    Append to our existing stream over SMB1 protocol. Specify an offset that will
    cause resuling xattr to exceed 64KiB default xattr size limit in Linux.
    """
    depends(request, ["STREAM_WRITTEN_SMB1"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=True)
    fd = c.create_file("streamstestfile:smb1_stream", "w")
    c.write(fd, b'test2', 131072)
    c.close(fd)

    fd2 = c.create_file("streamstestfile:smb1_stream", "w")
    contents = c.read(fd2, 131072, 5)
    c.close(fd2)
    c.disconnect()
    assert (contents.decode() == "test2")


def test_067_stream_delete_on_close_smb1(request):
    """
    Set delete_on_close on alternate datastream over SMB1 protocol, close, then verify
    stream was deleted.

    TODO: I have open MR to expand samba python bindings to support stream enumeration.
    Verifcation of stream deletion will have to be added once this is merged.
    """
    depends(request, ["STREAM_WRITTEN_SMB1", "LARGE_STREAM_WRITTEN_SMB1"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=True)
    fd = c.create_file("streamstestfile:smb1_stream", "w")
    c.close(fd, True)

    c.disconnect()


def test_068_case_insensitive_rename(request):
    """
    ZFS is case sensitive, but case preserving when casesensitivity == insensitive

    rename of to_rename -> To_rename should succeed and new file appear
    correctly in directory listing.

    Will fail with NT_STATUS_OBJECT_NAME_COLLISION if we have regression and
    samba identifies files as same.
    """
    depends(request, ["SHARE_IS_WRITABLE"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=True)
    fd = c.create_file("to_rename", "w")
    c.close(fd)
    c.rename("to_rename", "To_rename")
    files = [x['name'] for x in c.ls('\\')]
    c.disconnect()
    assert ("To_rename" in files)


def test_069_normal_rename(request):
    """
    This verifies that renames are successfully completed
    """
    depends(request, ["SHARE_IS_WRITABLE"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=True)
    fd = c.create_file("old_file_to_rename", "w")
    c.close(fd)
    c.rename("old_file_to_rename", "renamed_new_file")
    files = [x['name'] for x in c.ls('\\')]
    c.disconnect()
    assert ("renamed_new_file" in files)


"""
At this point we grant SMB_USER SeDiskOperatorPrivilege by making it a member
of the local group builtin_administrators. This privilege is required to manipulate
SMB quotas.
"""


@pytest.mark.dependency(name="BA_ADDED_TO_USER")
def test_089_add_to_builtin_admins(request):
    depends(request, ["SHARE_IS_WRITABLE"])
    smbuser_id = TEST_DATA['user']['id']
    ba = GET('/group?group=builtin_administrators').json()
    assert len(ba) != 0

    userinfo = GET(f'/user/id/{smbuser_id}').json()
    groups = userinfo['groups']
    groups.append(ba[0]['id'])

    payload = {'groups': groups}
    results = PUT(f"/user/id/{smbuser_id}/", payload)
    assert results.status_code == 200, f"res: {results.text}, payload: {payload}"


@pytest.mark.parametrize('proto', ["SMB2"])
def test_090_test_auto_smb_quota(request, proto):
    """
    Since the share is configured wtih ixnas:base_user_quota parameter,
    the first SMB tree connect should have set a ZFS user quota on the
    underlying dataset. Test querying through the SMB protocol.

    Currently SMB1 protocol is disabled because of hard-coded check in
    source3/smbd/nttrans.c to only allow root to get/set quotas.
    """
    depends(request, ["BA_ADDED_TO_USER"])
    c = SMB()
    qt = c.get_quota(
        host=ip,
        share=SMB_NAME,
        username=SMB_USER,
        password=SMB_PWD,
        smb1=(proto == "SMB1")
    )

    # There should only be one quota entry
    assert len(qt) == 1, qt

    # username is prefixed with server netbios name "SERVER\user"
    assert qt[0]['user'].endswith(SMB_USER), qt

    # Hard and Soft limits should be set to value above (1GiB)
    assert qt[0]['soft_limit'] == (2 ** 30), qt
    assert qt[0]['hard_limit'] == (2 ** 30), qt


def test_091_remove_auto_quota_param(request):
    depends(request, ["SMB_SHARE_CREATED"])
    call('sharing.smb.update', TEST_DATA['share']['id'], {
        'auxsmbconf': ''
    })


@pytest.mark.parametrize('proto', ["SMB2"])
def test_092_set_smb_quota(request, proto):
    """
    This test checks our ability to set a ZFS quota
    through the SMB protocol by first setting a 2 GiB
    quota, then reading it through the SMB protocol, then
    resetting to zero.
    """
    depends(request, ["BA_ADDED_TO_USER"])
    new_quota = 2 * (2**30)
    c = SMB()
    qt = c.set_quota(
        host=ip,
        share=SMB_NAME,
        username=SMB_USER,
        password=SMB_PWD,
        hardlimit=new_quota,
        target=SMB_USER,
        smb1=(proto == "SMB1")
    )
    assert len(qt) == 1, qt
    assert qt[0]['user'].endswith(SMB_USER), qt
    assert qt[0]['soft_limit'] == new_quota, qt
    assert qt[0]['hard_limit'] == new_quota, qt

    qt = c.get_quota(
        host=ip,
        share=SMB_NAME,
        username=SMB_USER,
        password=SMB_PWD,
        smb1=(proto == "SMB1")
    )
    assert len(qt) == 1, qt
    assert qt[0]['user'].endswith(SMB_USER), qt
    assert qt[0]['soft_limit'] == new_quota, qt
    assert qt[0]['hard_limit'] == new_quota, qt

    qt = c.set_quota(
        host=ip,
        share=SMB_NAME,
        username=SMB_USER,
        password=SMB_PWD,
        hardlimit=-1,
        target=SMB_USER,
        smb1=(proto == "SMB1")
    )
    assert len(qt) == 1, qt
    assert qt[0]['user'].endswith(SMB_USER), qt
    assert qt[0]['soft_limit'] is None, qt
    assert qt[0]['hard_limit'] is None, qt

    qt = c.get_quota(
        host=ip,
        share=SMB_NAME,
        username=SMB_USER,
        password=SMB_PWD,
        smb1=(proto == "SMB1")
    )
    assert len(qt) == 1, qt
    assert qt[0]['user'].endswith(SMB_USER), qt
    assert qt[0]['soft_limit'] is None, qt
    assert qt[0]['hard_limit'] is None, qt


def test_95_strip_quota(request):
    """
    This test removes any quota set for the test smb user
    """
    depends(request, ["BA_ADDED_TO_USER"])
    call('pool.dataset.set_quota', TEST_DATA['dataset'], [{
        'quota_type': 'USER',
        'id': SMB_USER,
        'quota_value': 0
    }])


@pytest.mark.dependency(name="AFP_ENABLED")
def test_140_enable_aapl(request):
    depends(request, ["SMB_SHARE_CREATED"])
    call('smb.update', {'aapl_extensions': True})
    call('sharing.smb.update', TEST_DATA['share']['id'], {
        'afp': True,
    })


@pytest.mark.dependency(name="SSH_XATTR_SET")
@pytest.mark.parametrize('xat', AFPXattr.keys())
def test_151_set_xattr_via_ssh(request, xat):
    """
    Iterate through AFP xattrs and set them on testfile
    via SSH.
    """
    depends(request, ["AFP_ENABLED"], scope="session")
    smb_path = TEST_DATA['share']['path']
    afptestfile = f'{smb_path}/afp_xattr_testfile'
    cmd = f'touch {afptestfile} && chown {SMB_USER} {afptestfile} && '
    cmd += f'echo -n \"{AFPXattr[xat]["text"]}\" | base64 -d | '
    cmd += f'attr -q -s {xat} {afptestfile}'

    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, {"cmd": cmd, "res": results['output']}


@pytest.mark.dependency(name="XATTR_CHECK_SMB_READ")
@pytest.mark.parametrize('xat', AFPXattr.keys())
def test_152_check_xattr_via_smb(request, xat):
    """
    Read xattr that was written via SSH and verify that
    data is same when viewed over SMB.
    """
    depends(request, ["SSH_XATTR_SET"])
    afptestfile = f'afp_xattr_testfile:{AFPXattr[xat]["smbname"]}'
    bytes = AFPXattr[xat]["smb_bytes"] if xat == "org.netatalk.Metadata" else AFPXattr[xat]["bytes"]
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=False)
    fd = c.create_file(afptestfile, "w")
    xat_bytes = c.read(fd, 0, len(bytes) + 1)
    c.close(fd)
    c.disconnect()

    err = {
        "name": xat,
        "b64data": b64encode(bytes)
    }

    # Python base64 library appends a `\t` to end of byte string
    assert xat_bytes == bytes, str(err)


@pytest.mark.dependency(name="XATTR_CHECK_SMB_UNLINK")
@pytest.mark.parametrize('xat', AFPXattr.keys())
def test_153_unlink_xattr_via_smb(request, xat):
    """
    Open AFP xattr, set "delete on close" flag, then close.
    """
    depends(request, ["XATTR_CHECK_SMB_READ"])
    afptestfile = f'afp_xattr_testfile:{AFPXattr[xat]["smbname"]}'
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=False)
    fd = c.create_file(afptestfile, "w")
    c.close(fd, True)
    c.disconnect()


@pytest.mark.dependency(name="XATTR_CHECK_SMB_WRITE")
@pytest.mark.parametrize('xat', AFPXattr.keys())
def test_154_write_afp_xattr_via_smb(request, xat):
    """
    Write xattr over SMB
    """
    depends(request, ["XATTR_CHECK_SMB_UNLINK"])
    afptestfile = f'afp_xattr_testfile:{AFPXattr[xat]["smbname"]}'
    payload = AFPXattr[xat]["smb_bytes"] if xat == "org.netatalk.Metadata" else AFPXattr[xat]["bytes"]
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=False)
    fd = c.create_file(afptestfile, "w")
    c.write(fd, payload)
    c.close(fd)
    c.disconnect()


@pytest.mark.parametrize('xat', AFPXattr.keys())
def test_155_ssh_read_afp_xattr(request, xat):
    """
    Read xattr that was set via SMB protocol directly via
    SSH and verify that data is the same.
    """
    depends(request, ["XATTR_CHECK_SMB_WRITE"], scope="session")
    # Netatalk-compatible xattr gets additional
    # metadata written to it, which makes comparison
    # of all bytes problematic.
    if xat == "org.netatalk.Metadata":
        return

    smb_path = TEST_DATA['share']['path']
    afptestfile = f'{smb_path}/afp_xattr_testfile'
    cmd = f'attr -q -g {xat} {afptestfile} | base64'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    xat_data = b64decode(results['stdout'])
    assert AFPXattr[xat]['bytes'] == xat_data, results['output']


def test_175_check_external_path(request):
    with smb_share(f'EXTERNAL:{ip}\\{SMB_NAME}', 'EXTERNAL'):
        with smb_connection(
            host=ip,
            share=SMB_NAME,
            username=SMB_USER,
            password=SMB_PWD,
            smb1=False
        ) as c:
            fd = c.create_file('external_test_file', "w")
            c.write(fd, b'EXTERNAL_TEST')
            c.close(fd)

        cmd = f'smbclient //127.0.0.1/EXTERNAL -U {SMB_USER}%{SMB_PWD} '
        cmd += '-c "get external_test_file"'
        ssh(cmd)

        results = SSH_TEST('cat external_test_file', user, password, ip)
        assert results['result'] is True, results['output']
        assert results['stdout'] == 'EXTERNAL_TEST'


def test_176_check_dataset_auto_create(request):
    with dataset('smb_proto_nested_datasets', data={'share_type': 'SMB'}) as ds:
        ds_mp = os.path.join('/mnt', ds)
        with smb_share(ds_mp, 'DATASETS', {'purpose': 'PRIVATE_DATASETS'}):
            with smb_connection(
                host=ip,
                share='DATASETS',
                username=SMB_USER,
                password=SMB_PWD,
                smb1=False
            ) as c:
                fd = c.create_file('nested_test_file', "w")
                c.write(fd, b'EXTERNAL_TEST')
                c.close(fd)

        acl = call('filesystem.getacl', os.path.join(ds_mp, SMB_USER), True)
        assert acl['trivial'] is False, str(acl)


def test_180_create_share_multiple_dirs_deep(request):
    depends(request, ["SMB_USER_CREATED"])
    with dataset('nested_dirs', data={'share_type': 'SMB'}) as ds:
        dirs_path = f'{ds["mountpoint"]}/d1/d2/d3'
        ssh(f'mkdir -p {dirs_path}')

        with smb_share(dirs_path, 'DIRS'):
            with smb_connection(
                host=ip,
                share='DIRS',
                username=SMB_USER,
                password=SMB_PWD,
                smb1=False
            ) as c:
                fd = c.create_file('nested_dirs_file', "w")
                c.write(fd, b'DIRS_TEST')
                c.close(fd)

        call('filesystem.stat', os.path.join(dirs_path, 'nested_dirs_file'))


def test_181_create_and_disable_share(request):
    depends(request, ["SMB_USER_CREATED"])
    with dataset('smb_disabled', data={'share_type': 'SMB'}) as ds:
        with smb_share(os.path.join('/mnt', ds), 'TO_DISABLE') as tmp_share:
            with smb_connection(
                host=ip,
                share='TO_DISABLE',
                username=SMB_USER,
                password=SMB_PWD,
                smb1=False
            ) as c:
                call('sharing.smb.update', tmp_share['id'], {'enabled': False})
                try:
                    c.create_file('canary', "w")
                except NTSTATUSError as status:
                    assert status.args[0] == ntstatus.NT_STATUS_NETWORK_NAME_DELETED, str(status)
                else:
                    assert c.connected is True
