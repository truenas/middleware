import os
import pytest

from contextlib import contextmanager
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
        }):
            with smb_share(os.path.join('/mnt', ds), SMB_NAME) as s:
                try:
                    call('service.control', 'START', 'cifs', job=True)
                    yield {'dataset': ds, 'share': s}
                finally:
                    call('service.control', 'STOP', 'cifs', job=True)


@contextmanager
def server_encryption(param):
    call('smb.update', {'encryption': param})

    try:
        yield
    finally:
        call('smb.update', {'encryption': 'DEFAULT'})


def test__smb_client_encrypt_default(smb_setup):
    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
        encryption='DEFAULT'
    ) as c:
        # perform basic op to fully initialize SMB session
        assert c.get_smb_encryption() == 'DEFAULT'

        c.ls('/')
        smb_status = call('smb.status')[0]

        # check session
        assert smb_status['encryption']['cipher'] == '-'
        assert smb_status['encryption']['degree'] == 'none'

        # check share
        assert smb_status['share_connections'][0]['encryption']['cipher'] == '-'
        assert smb_status['share_connections'][0]['encryption']['degree'] == 'none'


def test__smb_client_encrypt_desired(smb_setup):
    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
        encryption='DESIRED'
    ) as c:
        assert c.get_smb_encryption() == 'DESIRED'

        # perform basic op to fully initialize SMB session
        c.ls('/')
        smb_status = call('smb.status')[0]

        # check session
        assert smb_status['encryption']['cipher'] == 'AES-128-GCM'
        assert smb_status['encryption']['degree'] == 'partial'

        # check share
        assert smb_status['share_connections'][0]['encryption']['cipher'] == 'AES-128-GCM'
        assert smb_status['share_connections'][0]['encryption']['degree'] == 'full'


def test__smb_client_encrypt_required(smb_setup):
    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
        encryption='REQUIRED'
    ) as c:
        assert c.get_smb_encryption() == 'REQUIRED'

        # perform basic op to fully initialize SMB session
        c.ls('/')
        smb_status = call('smb.status')[0]

        # check session
        assert smb_status['encryption']['cipher'] == 'AES-128-GCM'
        assert smb_status['encryption']['degree'] == 'partial'

        # check share
        assert smb_status['share_connections'][0]['encryption']['cipher'] == 'AES-128-GCM'
        assert smb_status['share_connections'][0]['encryption']['degree'] == 'full'


@pytest.mark.parametrize('enc_param', ('DESIRED', 'REQUIRED'))
def test__smb_client_server_encrypt(smb_setup, enc_param):
    with server_encryption(enc_param):
        with smb_connection(
            share=smb_setup['share']['name'],
            username=SHAREUSER,
            password=PASSWD,
            encryption='DEFAULT'
        ) as c:
            # check that client credential desired encryption is
            # set to expected value
            assert c.get_smb_encryption() == 'DEFAULT'

            # perform basic op to fully initialize SMB session
            c.ls('/')
            smb_status = call('smb.status')[0]

            # check session
            assert smb_status['encryption']['cipher'] == 'AES-128-GCM'
            assert smb_status['encryption']['degree'] == 'full'

            # check share
            assert smb_status['share_connections'][0]['encryption']['cipher'] == 'AES-128-GCM'
            assert smb_status['share_connections'][0]['encryption']['degree'] == 'full'
