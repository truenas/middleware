import os
import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call

from protocols import smb_connection

SHAREUSER = 'CamelCamel'
PASSWD = 'abcd1234'
SMB_NAME = 'camel_share'


@pytest.fixture(scope='module')
def smb_setup(request):
    with dataset('smb-camel', data={'share_type': 'SMB'}) as ds:
        with user({
            'username': SHAREUSER,
            'full_name': SHAREUSER,
            'group_create': True,
            'password': PASSWD
        }):
            with smb_share(os.path.join('/mnt', ds), SMB_NAME) as s:
                try:
                    call('service.control', 'START', 'cifs', job=True)
                    yield {'dataset': ds, 'share': s}
                finally:
                    call('service.control', 'STOP', 'cifs', job=True)


def test__smb_auth_camel(smb_setup):
    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
    ) as c:
        # perform basic op to fully initialize SMB session
        c.ls('/')
