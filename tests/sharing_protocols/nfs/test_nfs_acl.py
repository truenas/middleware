import pytest

from middlewared.test.integration.assets.nfs import nfs_server
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, password
from middlewared.test.integration.utils.client import truenas_server
from protocols import SSH_NFS, nfs_share


@pytest.fixture(scope='module')
def start_nfs():
    with nfs_server():
        yield


TEST_PERMS = {
    "READ_DATA": True,
    "WRITE_DATA": True,
    "EXECUTE": True,
    "APPEND_DATA": True,
    "DELETE_CHILD": True,
    "DELETE": True,
    "READ_ATTRIBUTES": True,
    "WRITE_ATTRIBUTES": True,
    "READ_NAMED_ATTRS": True,
    "WRITE_NAMED_ATTRS": True,
    "READ_ACL": True,
    "WRITE_ACL": True,
    "WRITE_OWNER": True,
    "SYNCHRONIZE": True,
}

TEST_FLAGS = {
    "FILE_INHERIT": True,
    "DIRECTORY_INHERIT": True,
    "INHERIT_ONLY": False,
    "NO_PROPAGATE_INHERIT": False,
    "INHERITED": False,
}


@pytest.mark.timeout(600)
@pytest.mark.parametrize("version,test_acl_flag", [
    pytest.param(4.2, True, id="NFSv4.2"),
    pytest.param(4.1, True, id="NFSv4.1"),
    pytest.param(4.0, False, id="NFSv4.0"),
])
def test_nfsv4_acl_support(start_nfs, version, test_acl_flag):
    """
    Validate reading and setting NFSv4 ACLs through an NFSv4 mount for
    NFSv4.2, NFSv4.1, and NFSv4.0:
    1) Create and locally mount an NFSv4 share on the TrueNAS server.
    2) Iterate through all permissions options: set via NFS client, read back
       via NFS client, and verify via filesystem API.
    3) Repeat for each supported ACE flag.
    4) For NFSv4.1/NFSv4.2, repeat for each supported acl_flag.
    """
    theacl = [
        {"tag": "owner@", "id": -1, "perms": TEST_PERMS.copy(), "flags": TEST_FLAGS.copy(), "type": "ALLOW"},
        {"tag": "group@", "id": -1, "perms": TEST_PERMS.copy(), "flags": TEST_FLAGS.copy(), "type": "ALLOW"},
        {"tag": "everyone@", "id": -1, "perms": TEST_PERMS.copy(), "flags": TEST_FLAGS.copy(), "type": "ALLOW"},
        {"tag": "USER", "id": 65534, "perms": TEST_PERMS.copy(), "flags": TEST_FLAGS.copy(), "type": "ALLOW"},
        {"tag": "GROUP", "id": 666, "perms": TEST_PERMS.copy(), "flags": TEST_FLAGS.copy(), "type": "ALLOW"},
    ]

    # Use version-specific dataset name so a cleanup failure in one version
    # does not prevent other versions from running.
    ds_name = f'test_nfs4_acl_v{str(version).replace(".", "_")}'

    with dataset(ds_name, data={"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}) as ds:
        acl_nfs_path = f'/mnt/{ds}'
        call('filesystem.setacl', {
            'path': acl_nfs_path,
            'dacl': theacl,
            'options': {'validate_effective_acl': False},
        }, job=True)
        with nfs_share(acl_nfs_path):
            with SSH_NFS(truenas_server.ip, acl_nfs_path, vers=version,
                         user='root', password=password(), ip=truenas_server.ip) as n:
                nfsacl = n.getacl(".")
                for idx, ace in enumerate(nfsacl):
                    assert ace == theacl[idx], str(ace)

                for perm in TEST_PERMS:
                    if perm == 'SYNCHRONIZE':
                        # Break on SYNCHRONIZE due to Linux tool limitation
                        break

                    theacl[4]['perms'][perm] = False
                    n.setacl(".", theacl)
                    nfsacl = n.getacl(".")
                    for idx, ace in enumerate(nfsacl):
                        assert ace == theacl[idx], str(ace)

                    result = call('filesystem.getacl', acl_nfs_path, False)
                    for idx, ace in enumerate(result['acl']):
                        assert ace == {**nfsacl[idx], "who": None}, str(ace)

                for flag in ("INHERIT_ONLY", "NO_PROPAGATE_INHERIT"):
                    theacl[4]['flags'][flag] = True
                    n.setacl(".", theacl)
                    nfsacl = n.getacl(".")
                    for idx, ace in enumerate(nfsacl):
                        assert ace == theacl[idx], str(ace)

                    result = call('filesystem.getacl', acl_nfs_path, False)
                    for idx, ace in enumerate(result['acl']):
                        assert ace == {**nfsacl[idx], "who": None}, str(ace)

                if test_acl_flag:
                    assert 'none' == n.getaclflag(".")
                    for acl_flag in ['auto-inherit', 'protected', 'defaulted']:
                        n.setaclflag(".", acl_flag)
                        assert acl_flag == n.getaclflag(".")

                        result = call('filesystem.getacl', acl_nfs_path, False)

                        # Normalize flag name for comparison to plugin equivalent
                        flag_is_set = 'autoinherit' if acl_flag == 'auto-inherit' else acl_flag

                        nfs41_flags = result['aclflags']
                        for flag in ['autoinherit', 'protected', 'defaulted']:
                            if flag == flag_is_set:
                                assert nfs41_flags[flag], nfs41_flags
                            else:
                                assert not nfs41_flags[flag], nfs41_flags
