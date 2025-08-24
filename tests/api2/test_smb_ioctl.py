import pytest
import random

from dataclasses import asdict
from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.pool import dataset

from protocols import smb_connection
from protocols.SMB import (
    FsctlQueryFileRegionsRequest,
    FileRegionInfo,
    FileUsage,
)

from samba import ntstatus
from samba import NTSTATUSError

SHARE_NAME = 'ioctl_share'


@pytest.fixture(scope='module')
def setup_smb_tests(request):
    with dataset('smbclient-testing', data={'share_type': 'SMB'}) as ds:
        with user({
            'username': 'smbuser',
            'full_name': 'smbuser',
            'group_create': True,
            'password': 'Abcd1234'
        }) as u:
            with smb_share(os.path.join('/mnt', ds), SHARE_NAME) as s:
                try:
                    call('service.start', 'cifs')
                    yield {'dataset': ds, 'share': s, 'user': u}
                finally:
                    call('service.stop', 'cifs')


def test__query_file_regions_normal(setup_smb_tests):
    ds, share, smb_user = setup_smb_tests
    with smb_connection(
        share=SHARE_NAME,
        username=smbuser['username'],
        password='Abcd1234',
        smb1=False
    ) as c:
        fd = c.create_file("file_regions_normal", "w")
        buf = random.randbytes(1024)

        for offset in range(0, 128):
            c.write(fd, offset=offset * 1024, data=buf)

        # First get with region omitted. This should return entire file
        fsctl_request_null_region = FsctlQueryFileRegionsRequest(region=None)
        fsctl_resp = c.fsctl(fd, fsctl_request_null_region)

        assert fsctl_resp.flags == 0
        assert fsctl_resp.total_region_entry_count == 1
        assert fsctl_resp.region_entry_count == 1
        assert fsctl_resp.reserved == 1
        assert fsctl_resp.region is not None

        assert fsctl_resp.region.offset == 0
        assert fsctl_resp.region.length == 128 * 1024
        assert fsctl_resp.region.desired_usage == FileUsage.VALID_CACHED_DATA
        assert fsctl_resp.region.reserved == 0

        # Take same region we retrieved from server and use with new request
        fsctl_request_with_region = FsctlQueryFileRegionsRequest(region=fsctl_resp.region)
        fsctl_resp2 = c.fsctl(fd, fsctl_request_with_region)

        assert asdict(fsctl_resp) == asdict(fsctl_resp2)


def test__query_file_regions_with_holes(setup_smb_tests):
    ds, share, smb_user = setup_smb_tests
    with smb_connection(
        share=SHARE_NAME,
        username=smbuser['username'],
        password='Abcd1234',
        smb1=False
    ) as c:
        fd = c.create_file("file_regions_normal", "w")
        buf = random.randbytes(4096)

        # insert some holes in file
        for offset in range(0, 130):
            if offset % 2 == 0:
                c.write(fd, offset=offset * 4096, data=buf)

        fsctl_request_null_region = FsctlQueryFileRegionsRequest(region=None)
        fsctl_resp = c.fsctl(fd, fsctl_request_null_region)

        assert fsctl_resp.flags == 0
        assert fsctl_resp.total_region_entry_count == 1
        assert fsctl_resp.region_entry_count == 1
        assert fsctl_resp.reserved == 1
        assert fsctl_resp.region is not None

        assert fsctl_resp.region.offset == 0
        assert fsctl_resp.region.length == 128 * 4096
        assert fsctl_resp.region.desired_usage == FileUsage.VALID_CACHED_DATA
        assert fsctl_resp.region.reserved == 0

        # Take same region we retrieved from server and use with new request
        fsctl_request_with_region = FsctlQueryFileRegionsRequest(region=fsctl_resp.region)
        fsctl_resp2 = c.fsctl(fd, fsctl_request_with_region)

        assert asdict(fsctl_resp) == asdict(fsctl_resp2)


def test__query_file_regions_trailing_zeroes(setup_smb_tests):
    """
    FileRegionInfo should contain Valid Data Length which is length in bytes of data
    that has been written to the file in the specified region, from the beginning of
    the region untile the last byte that has not been zeroed or uninitialized
    """
    ds, share, smb_user = setup_smb_tests
    with smb_connection(
        share=SHARE_NAME,
        username=smbuser['username'],
        password='Abcd1234',
        smb1=False
    ) as c:
        fd = c.create_file("file_regions_normal", "w")
        buf = random.randbytes(4096)

        # insert a hole in file
        c.write(fd, offset=0, data=buf)
        c.write(fd, offset=8192, data=buf)

        # requesting entire file should give full length
        fsctl_request_null_region = FsctlQueryFileRegionsRequest(region=None)
        fsctl_resp = c.fsctl(fd, fsctl_request_null_region)
        assert fsctl_resp.region.length == 12288

        # requesting region that has hole at end of it should only give data length
        limited_region = FileRegionInfo(offset=0, length=8192)
        fsctl_request_limited_region = FsctlQueryFileRegionsRequest(region=limited_region)
        fsctl_resp = c.fsctl(fd, fsctl_request_limited_region)
        assert fsctl_resp.region.offset == 0
        assert fsctl_resp.region.length == 4096
