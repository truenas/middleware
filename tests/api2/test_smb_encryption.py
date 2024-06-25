import os
import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call

from protocols import smb_connection

SHAREUSER = 'smbuser420'
PASSWD = 'abcd1234'
SMB_NAME = 'enc_share'


@pytest.fixture(scope='module')
def smb_setup(request):
    with dataset('smb-encrypt', data={'share_type': 'SMB'}) as ds:
        with user({
            'username': SHAREUSER,
            'full_name': SHAREUSER,
            'group_create': True,
            'password': PASSWD
        }, get_instance=False):
            with smb_share(os.path.join('/mnt', ds), SMB_NAME) as s:
                try:
                    call('service.start', 'cifs')
                    yield {'dataset': ds, 'share': s}
                finally:
                    call('service.stop', 'cifs')


def test__smb_client_encrypt_default(smb_setup):
    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
        encrypt='DEFAULT'
    ) as c:
        # perform basic op to fully initialize SMB session
        c.ls('/')
        smb_status = call('smb.status')[0]

        # check IPC
        assert smb_status['encyption']['cipher'] == '-'
        assert smb_status['cipher']['degree'] == 'none'

        # check share
        assert smb_status['share_connections'][0]['cipher'] == '-'
        assert smb_status['share_connections'][0]['degree'] == 'none'


def test__smb_client_encrypt_desired(smb_setup):
    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
        encrypt='DESIRED'
    ) as c:
        # perform basic op to fully initialize SMB session
        c.ls('/')
        smb_status = call('smb.status')[0]

        # check IPC
        assert smb_status['encyption']['cipher'] == 'AES-128-GCM'
        assert smb_status['cipher']['degree'] == 'partial'

        # check share
        assert smb_status['share_connections'][0]['cipher'] == 'AES-128-GCM'
        assert smb_status['share_connections'][0]['degree'] == 'full'


def test__smb_client_encrypt_required(smb_setup):
    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
        encrypt='REQUIRED'
    ) as c:
        # perform basic op to fully initialize SMB session
        c.ls('/')
        smb_status = call('smb.status')[0]

        # check IPC
        assert smb_status['encyption']['cipher'] == 'AES-128-GCM'
        assert smb_status['cipher']['degree'] == 'partial'

        # check share
        assert smb_status['share_connections'][0]['cipher'] == 'AES-128-GCM'
        assert smb_status['share_connections'][0]['degree'] == 'full'
