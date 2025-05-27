import contextlib

import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, ssh
from protocols import SMB
from samba import ntstatus, NTSTATUSError


SMB_PASSWORD = 'Abcd1234'
SMB_USER = 'smbuser999'


def passphrase_encryption():
    return {
        'encryption_options': {
            'generate_key': False,
            'pbkdf2iters': 100000,
            'algorithm': 'AES-128-CCM',
            'passphrase': 'passphrase',
        },
        'encryption': True,
        'inherit_encryption': False,
    }

def lock_dataset(name):
    payload = {
        'force_umount': True
    }
    assert call('pool.dataset.lock', name, payload, job=True)


def unlock_dataset(name, options=None):
    payload = {
        'recursive': True,
        'datasets': [
            {
                'name': name,
                'passphrase': 'passphrase'
            }
        ],
        **(options or {}),
    }
    result = call('pool.dataset.unlock', name, payload, job=True)
    assert result['unlocked'] == [name], str(result)


@contextlib.contextmanager
def smb_connection(**kwargs):
    c = SMB()
    c.connect(**kwargs)

    try:
        yield c
    finally:
        c.disconnect()


@pytest.fixture(scope='module')
def smb_user():
    with user({
        'username': SMB_USER,
        'full_name': 'doug',
        'group_create': True,
        'password': SMB_PASSWORD,
        'smb': True
    }) as u:
        yield u


@pytest.mark.parametrize('toggle_attachments', [True, False])
def test_pool_dataset_unlock_smb(smb_user, toggle_attachments):
    with (
        # Prepare test SMB share
        dataset('normal', mode='777') as normal,
        smb_share(f'/mnt/{normal}', 'normal', {'purpose': 'LEGACY_SHARE', 'options': {'guestok': True}}),
        # Create an encrypted SMB share, unlocking which might lead to SMB service interruption
        dataset('encrypted', passphrase_encryption(), mode='777') as encrypted,
        smb_share(f'/mnt/{encrypted}', 'encrypted', {'purpose': 'LEGACY_SHARE', 'options': {'guestok': True}})
    ):
        ssh(f'touch /mnt/{encrypted}/secret')
        assert call('service.control', 'START', 'cifs', job=True)
        lock_dataset(encrypted)
        # Mount test SMB share
        with smb_connection(
            share='normal',
            username=SMB_USER,
            password=SMB_PASSWORD
        ) as normal_connection:
            # Locked share should not be mountable
            with pytest.raises(NTSTATUSError) as e:
                with smb_connection(
                    share='encrypted',
                    username=SMB_USER,
                    password=SMB_PASSWORD
                ):
                    pass

            assert e.value.args[0] == ntstatus.NT_STATUS_BAD_NETWORK_NAME

            conn = normal_connection.show_connection()
            assert conn['connected'], conn
            unlock_dataset(encrypted, {'toggle_attachments': toggle_attachments})

            conn = normal_connection.show_connection()
            assert conn['connected'], conn

        if toggle_attachments:
            # We should be able to mount encrypted share
            with smb_connection(
                share='encrypted',
                username=SMB_USER,
                password=SMB_PASSWORD
            ) as encrypted_connection:
                assert [x['name'] for x in encrypted_connection.ls('')] == ['secret']
        else:
            # We should still not be able to mount encrypted share as we did not reload attachments
            with pytest.raises(NTSTATUSError) as e:
                with smb_connection(
                    share='encrypted',
                    username=SMB_USER,
                    password=SMB_PASSWORD
                ):
                    pass

            assert e.value.args[0] == ntstatus.NT_STATUS_BAD_NETWORK_NAME

    assert call('service.control', 'STOP', 'cifs', job=True)
