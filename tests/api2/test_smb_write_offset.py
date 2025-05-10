import os
import pytest
import random

from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call

from protocols import smb_connection

from samba import ntstatus
from samba import NTSTATUSError

SHARE_NAME = 'offset_test'

LARGE_OFFSET = 0x0000140000000000
INVALID_OFFSET = 0x0000410000000000


@pytest.fixture(scope='module')
def setup_smb_tests():
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


def test_valid_offset(setup_smb_tests):
    ds, share, smb_user = setup_smb_tests
    with smb_connection(
        share=SHARE_NAME,
        username=smb_user['username'],
        password='Abcd1234',
        smb1=False
    ) as c:
        fd = c.create_file('file_valid_offset', 'w')
        buf = random.randbytes(1024)

        c.write(fd, offset=LARGE_OFFSET, data=buf)
        out = c.read(fd, offset=LARGE_OFFSET, cnt=1024)
        assert buf == out


def test_invalid_offset(setup_smb_tests):
    ds, share, smb_user = setup_smb_tests
    with smb_connection(
        share=SHARE_NAME,
        username=smb_user['username'],
        password='Abcd1234',
        smb1=False
    ) as c:
        fd = c.create_file('file_valid_offset', 'w')

        with pytest.raises(NTSTATUSError) as nt_err:
            c.write(fd, offset=INVALID_OFFSET, data=b'CANARY')

        assert nt_err.value.args[0] == ntstatus.NT_STATUS_INVALID_PARAMETER
