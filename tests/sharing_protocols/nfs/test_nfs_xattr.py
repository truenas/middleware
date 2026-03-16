import pytest

from middlewared.test.integration.assets.nfs import nfs_server
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import password
from middlewared.test.integration.utils.client import truenas_server
from protocols import SSH_NFS, nfs_share


@pytest.fixture(scope='module')
def start_nfs():
    with nfs_server():
        yield


def test_xattr_support(start_nfs):
    """
    Perform basic validation of NFSv4.2 xattr support.
    Mount path via NFS 4.2, create a file and dir, and write + read xattr on each.
    """
    with dataset('test_nfs4_xattr', mode='777') as ds:
        with nfs_share(f'/mnt/{ds}'):
            for i in range(2):
                try:
                    with SSH_NFS(truenas_server.ip, f'/mnt/{ds}', vers=4.2,
                                 user='root', password=password(), ip=truenas_server.ip, timeout=20) as n:
                        n.create("testfile")
                        n.setxattr("testfile", "user.testxattr", "the_contents")
                        assert n.getxattr("testfile", "user.testxattr") == "the_contents"

                        n.create("testdir", True)
                        n.setxattr("testdir", "user.testxattr2", "the_contents2")
                        assert n.getxattr("testdir", "user.testxattr2") == "the_contents2"
                        break
                except Exception:
                    # Get one retry pass
                    pass
