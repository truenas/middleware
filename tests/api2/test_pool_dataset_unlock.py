import contextlib
import urllib.parse

import pytest

from auto_config import pool_name
from middlewared.test.integration.assets.account import user
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


@contextlib.contextmanager
def dataset(name, options=None):
    assert '/' not in name

    dataset = f'{pool_name}/{name}'
    call('pool.dataset.create', {'name': dataset, **(options or {})})
    call('filesystem.setperm', {'path': f'/mnt/{dataset}', 'mode': '777'}, job=True)

    try:
        yield dataset
    finally:
        assert call('pool.dataset.delete', urllib.parse.quote(dataset, ""))


@contextlib.contextmanager
def smb_share(name, path, options=None):
    id = call('sharing.smb.create', {
        'name': name,
        'path': path,
        'guestok': True,
        **(options or {}),
    })['id']
    try:
        yield id
    finally:
        assert call('sharing.smb.delete', id)


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
    }, get_instance=True) as u:
        yield u


@pytest.mark.parametrize('toggle_attachments', [True, False])
def test_pool_dataset_unlock_smb(smb_user, toggle_attachments):
    with (
        # Prepare test SMB share
        dataset('normal') as normal,
        smb_share('normal', f'/mnt/{normal}'),
        # Create an encrypted SMB share, unlocking which might lead to SMB service interruption
        dataset('encrypted', passphrase_encryption()) as encrypted,
        smb_share('encrypted', f'/mnt/{encrypted}')
    ):
        ssh(f'touch /mnt/{encrypted}/secret')
        assert call('service.start', 'cifs')
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

    assert call('service.stop', 'cifs')
