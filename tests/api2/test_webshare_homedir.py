import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call



def test_webshare_is_home_base_field():
    """Test that webshare shares support the is_home_base field"""
    with dataset('webshare_is_home_base_test') as ds:
        # Create a share with is_home_base=False (default)
        share1 = call('sharing.webshare.create', {
            'name': 'Share1',
            'path': f'/mnt/{ds}',
            'is_home_base': False,
        })
        try:
            assert share1['is_home_base'] is False

            # Create a share with is_home_base=True
            share2 = call('sharing.webshare.create', {
                'name': 'Share2',
                'path': f'/mnt/{ds}',
                'is_home_base': True,
            })
            try:
                assert share2['is_home_base'] is True
            finally:
                call('sharing.webshare.delete', share2['id'])
        finally:
            call('sharing.webshare.delete', share1['id'])


def test_webshare_is_home_base_only_one_allowed():
    """Test that only one share can have is_home_base enabled"""
    with dataset('webshare_is_home_base_validation') as ds:
        # Create first share with is_home_base=True
        share1 = call('sharing.webshare.create', {
            'name': 'HomeShare',
            'path': f'/mnt/{ds}',
            'is_home_base': True,
        })

        try:
            # Try to create second share with is_home_base=True - should fail
            with pytest.raises(Exception) as exc_info:
                call('sharing.webshare.create', {
                    'name': 'AnotherHomeShare',
                    'path': f'/mnt/{ds}',
                    'is_home_base': True,
                })

            assert 'Only one share can be configured as home directory base' in str(exc_info.value)

            # Create second share with is_home_base=False - should succeed
            share2 = call('sharing.webshare.create', {
                'name': 'RegularShare',
                'path': f'/mnt/{ds}',
                'is_home_base': False,
            })

            try:
                assert share2['is_home_base'] is False

                # Try to update share2 to have is_home_base=True - should fail
                with pytest.raises(Exception) as exc_info:
                    call('sharing.webshare.update', share2['id'], {
                        'is_home_base': True,
                    })

                assert 'Only one share can be configured as home directory base' in str(exc_info.value)
            finally:
                call('sharing.webshare.delete', share2['id'])
        finally:
            call('sharing.webshare.delete', share1['id'])


def test_webshare_is_home_base_update_to_true():
    """Test updating a share to enable is_home_base when no other share has it"""
    with dataset('webshare_is_home_base_update') as ds:
        # Create share with is_home_base=False
        share = call('sharing.webshare.create', {
            'name': 'TestShare',
            'path': f'/mnt/{ds}',
            'is_home_base': False,
        })

        try:
            assert share['is_home_base'] is False

            # Update to is_home_base=True - should succeed
            updated_share = call('sharing.webshare.update', share['id'], {
                'is_home_base': True,
            })

            assert updated_share['is_home_base'] is True

            # Update back to is_home_base=False - should succeed
            updated_share = call('sharing.webshare.update', share['id'], {
                'is_home_base': False,
            })

            assert updated_share['is_home_base'] is False
        finally:
            call('sharing.webshare.delete', share['id'])
