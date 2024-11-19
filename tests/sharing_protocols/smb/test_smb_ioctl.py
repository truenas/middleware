import os
import pytest
import random

from dataclasses import asdict
from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call

from protocols import smb_connection
from protocols.smb_proto import (
    FsctlQueryFileRegionsRequest,
    FileRegionInfo,
    FileUsage,
    QFR_MAX_OUT,
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
                    call('service.control', 'START', 'cifs', job=True)
                    yield (ds, s, u)
                finally:
                    call('service.control', 'STOP', 'cifs', job=True)


def test__query_file_regions_normal(setup_smb_tests):
    ds, share, smbuser = setup_smb_tests
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
        fsctl_request_null_region = FsctlQueryFileRegionsRequest(region_info=None)
        fsctl_resp = c.fsctl(fd, fsctl_request_null_region, QFR_MAX_OUT)

        assert fsctl_resp.flags == 0
        assert fsctl_resp.total_region_entry_count == 1
        assert fsctl_resp.region_entry_count == 1
        assert fsctl_resp.reserved == 0
        assert fsctl_resp.region is not None

        assert fsctl_resp.region.offset == 0
        assert fsctl_resp.region.length == 128 * 1024
        assert fsctl_resp.region.desired_usage == FileUsage.VALID_CACHED_DATA
        assert fsctl_resp.region.reserved == 0

        # Take same region we retrieved from server and use with new request
        fsctl_request_with_region = FsctlQueryFileRegionsRequest(region_info=fsctl_resp.region)
        fsctl_resp2 = c.fsctl(fd, fsctl_request_with_region, QFR_MAX_OUT)

        assert asdict(fsctl_resp) == asdict(fsctl_resp2)


def test__query_file_regions_with_holes(setup_smb_tests):
    ds, share, smbuser = setup_smb_tests
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

        fsctl_request_null_region = FsctlQueryFileRegionsRequest(region_info=None)
        fsctl_resp = c.fsctl(fd, fsctl_request_null_region, QFR_MAX_OUT)

        assert fsctl_resp.flags == 0
        assert fsctl_resp.total_region_entry_count == 1
        assert fsctl_resp.region_entry_count == 1
        assert fsctl_resp.reserved == 0
        assert fsctl_resp.region is not None

        assert fsctl_resp.region.offset == 0
        assert fsctl_resp.region.length == 128 * 4096
        assert fsctl_resp.region.desired_usage == FileUsage.VALID_CACHED_DATA
        assert fsctl_resp.region.reserved == 0

        # Take same region we retrieved from server and use with new request
        fsctl_request_with_region = FsctlQueryFileRegionsRequest(region_info=fsctl_resp.region)
        fsctl_resp2 = c.fsctl(fd, fsctl_request_with_region, QFR_MAX_OUT)

        assert asdict(fsctl_resp) == asdict(fsctl_resp2)


def test__query_file_regions_trailing_zeroes(setup_smb_tests):
    """
    FileRegionInfo should contain Valid Data Length which is length in bytes of data
    that has been written to the file in the specified region, from the beginning of
    the region untile the last byte that has not been zeroed or uninitialized
    """
    ds, share, smbuser = setup_smb_tests
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
        fsctl_request_null_region = FsctlQueryFileRegionsRequest(region_info=None)
        fsctl_resp = c.fsctl(fd, fsctl_request_null_region, QFR_MAX_OUT)
        assert fsctl_resp.region.length == 12288

        # requesting region that has hole at end of it should only give data length
        limited_region = FileRegionInfo(offset=0, length=8192)
        fsctl_request_limited_region = FsctlQueryFileRegionsRequest(region_info=limited_region)
        fsctl_resp = c.fsctl(fd, fsctl_request_limited_region, QFR_MAX_OUT)
        assert fsctl_resp.region.offset == 0
        assert fsctl_resp.region.length == 4096


def test__query_file_regions_alternate_data_stream(setup_smb_tests):
    ds, share, smbuser = setup_smb_tests
    with smb_connection(
        share=SHARE_NAME,
        username=smbuser['username'],
        password='Abcd1234',
        smb1=False
    ) as c:
        fd = c.create_file("file_regions_stream_base", "w")
        buf = random.randbytes(4096)
        c.close(fd)

        fd = c.create_file("file_regions_stream_base:thestream", "w")
        buf = random.randbytes(4096)

        fsctl_request_null_region = FsctlQueryFileRegionsRequest(region_info=None)

        # requesting entire file should give full length
        with pytest.raises(NTSTATUSError) as e:
            fsctl_request_null_region = FsctlQueryFileRegionsRequest(region_info=None)
            c.fsctl(fd, fsctl_request_null_region, QFR_MAX_OUT)

        assert e.value.args[0] == ntstatus.NT_STATUS_INVALID_PARAMETER

