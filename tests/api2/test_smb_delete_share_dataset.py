import os
import pytest

from contextlib import contextmanager
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call

from protocols import smb_connection
from samba import ntstatus
from samba import NTSTATUSError

SHAREUSER = 'notintheface'
PASSWD = 'abcd1234'
SMB_NAME = 'delme'


@contextmanager
def create_share_ds():
    with dataset('delme', data={'share_type': 'SMB'}) as ds:
        with user({
            'username': SHAREUSER,
            'full_name': SHAREUSER,
            'group_create': True,
            'password': PASSWD
        }, get_instance=False):
            with smb_share(os.path.join('/mnt', ds), SMB_NAME) as s:
                try:
                    call('service.start', 'cifs', job=True)
                    yield {'dataset': ds, 'share': s}
                finally:
                    call('service.stop', 'cifs', job=True)


def test__smb_share_dataset_destroy():
    with create_share_ds() as smb_setup:
        with smb_connection(
            share=smb_setup['share']['name'],
            username=SHAREUSER,
            password=PASSWD,
        ) as c:
            # perform basic op to fully initialize SMB session
            c.mkdir('foo')

            call('pool.dataset.delete', smb_setup['dataset'])

            # Verify that middleware properly closed the share
            with pytest.raises(NTSTATUSError) as nterr:
                c.ls('/')

            assert nterr.value.args[0] == ntstatus.NT_STATUS_NETWORK_NAME_DELETED
