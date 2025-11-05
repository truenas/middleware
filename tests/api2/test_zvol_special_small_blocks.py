import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


_1GiB = 1073741824


def test_zvol_explicit_special_small_block_size():
    """
    Test that special_small_block_size can be explicitly set on zvols (ZFS 2.4 enhancement).
    Previously this property only worked on FILESYSTEM datasets.
    """
    with dataset('test_zvol_explicit_special', {
        'type': 'VOLUME',
        'volsize': _1GiB,
        'volblocksize': '128K',
        'special_small_block_size': 1048576  # 1MB
    }) as zvol:
        zvol_info = call('pool.dataset.get_instance', zvol)
        assert zvol_info['special_small_block_size']['value'] == '1048576'


def test_zvol_auto_protection_when_volblocksize_smaller_than_parent():
    """
    CRITICAL TEST: Automatic protection against unintended special vdev usage.

    When creating a zvol under a dataset with special_small_block_size set,
    if volblocksize < parent's threshold, ALL zvol I/O would go to special vdev.
    This is undesired, so middleware should automatically set special_small_block_size=0.
    """
    # Create parent dataset with special_small_block_size = 1MB
    with dataset('test_parent_special', {
        'type': 'FILESYSTEM',
        'special_small_block_size': 1048576  # 1MB
    }) as parent:
        # Create zvol with volblocksize=128K (smaller than 1MB parent threshold)
        zvol_name = f'{parent}/zvol_auto_protect'
        zvol = call('pool.dataset.create', {
            'name': zvol_name,
            'type': 'VOLUME',
            'volsize': _1GiB,
            'volblocksize': '128K'  # 128K < 1MB parent threshold
            # NOT setting special_small_block_size (will inherit by default)
        })

        try:
            # CRITICAL: Should be auto-set to 0 to prevent all I/O going to special vdev
            assert zvol['special_small_block_size']['value'] == '0'

            # Verify it was actually auto-protected (not inherited from parent)
            parent_info = call('pool.dataset.get_instance', parent)
            assert parent_info['special_small_block_size']['value'] == '1048576'

            # Zvol should have 0, not inherit the 1MB from parent
            zvol_check = call('pool.dataset.get_instance', zvol_name)
            assert zvol_check['special_small_block_size']['value'] == '0'
        finally:
            call('pool.dataset.delete', zvol_name)


def test_zvol_explicit_inherit_gets_auto_protected():
    """
    Test that explicit INHERIT is also protected when volblocksize < parent threshold.
    """
    with dataset('test_parent_inherit', {
        'type': 'FILESYSTEM',
        'special_small_block_size': 2097152  # 2MB
    }) as parent:
        zvol_name = f'{parent}/zvol_explicit_inherit'
        zvol = call('pool.dataset.create', {
            'name': zvol_name,
            'type': 'VOLUME',
            'volsize': _1GiB,
            'volblocksize': '64K',  # 64K < 2MB
            'special_small_block_size': 'INHERIT'  # Explicitly requesting inheritance
        })

        try:
            # Should still be auto-protected (set to 0 instead of inheriting)
            assert zvol['special_small_block_size']['value'] == '0'
        finally:
            call('pool.dataset.delete', zvol_name)


def test_zvol_no_auto_protection_when_volblocksize_larger_than_parent():
    """
    Test that when volblocksize >= parent threshold, auto-protection does NOT trigger.
    The zvol should be allowed to inherit or keep its value.
    """
    # Create parent with small threshold (16K)
    with dataset('test_parent_no_protect', {
        'type': 'FILESYSTEM',
        'special_small_block_size': 16384  # 16K
    }) as parent:
        # Create zvol with volblocksize=128K (larger than 16K parent threshold)
        zvol_name = f'{parent}/zvol_no_protect'
        zvol = call('pool.dataset.create', {
            'name': zvol_name,
            'type': 'VOLUME',
            'volsize': _1GiB,
            'volblocksize': '128K'  # 128K > 16K, so no auto-protection needed
        })

        try:
            # Should inherit parent's value (not auto-set to 0)
            # The zvol blocks (128K) are larger than threshold (16K), so they go to data vdevs anyway
            zvol_check = call('pool.dataset.get_instance', zvol_name)
            # Could be INHERIT or the actual inherited value
            assert zvol_check['special_small_block_size']['value'] in ('INHERIT', '16384')
        finally:
            call('pool.dataset.delete', zvol_name)


def test_zvol_explicit_value_not_overridden():
    """
    Test that when user explicitly sets special_small_block_size, it's NOT overridden
    by auto-protection, even if volblocksize < parent threshold.
    """
    with dataset('test_parent_explicit', {
        'type': 'FILESYSTEM',
        'special_small_block_size': 1048576  # 1MB
    }) as parent:
        zvol_name = f'{parent}/zvol_explicit_value'
        zvol = call('pool.dataset.create', {
            'name': zvol_name,
            'type': 'VOLUME',
            'volsize': _1GiB,
            'volblocksize': '128K',  # 128K < 1MB
            'special_small_block_size': 524288  # User explicitly sets 512K
        })

        try:
            # Should respect user's explicit value, NOT auto-set to 0
            assert zvol['special_small_block_size']['value'] == '524288'
        finally:
            call('pool.dataset.delete', zvol_name)


def test_zvol_parent_without_special_small_block_size():
    """
    Test that zvol creation works normally when parent doesn't have special_small_block_size set.
    """
    with dataset('test_parent_no_special', {
        'type': 'FILESYSTEM'
    }) as parent:
        zvol_name = f'{parent}/zvol_no_parent_special'
        zvol = call('pool.dataset.create', {
            'name': zvol_name,
            'type': 'VOLUME',
            'volsize': _1GiB,
            'volblocksize': '128K'
        })

        try:
            # Should work fine, no auto-protection needed
            assert zvol is not None
            # special_small_block_size should be 0 or INHERIT
            zvol_check = call('pool.dataset.get_instance', zvol_name)
            assert zvol_check['special_small_block_size']['value'] in ('0', 'INHERIT')
        finally:
            call('pool.dataset.delete', zvol_name)


@pytest.mark.parametrize(
    'value,valid', [
        (0, True),                          # Minimum value (disable special vdev)
        (512, True),                        # Small value
        (1048576, True),                    # 1MB (old maximum)
        (8388608, True),                    # 8MB (within new range)
        (16777216, True),                   # 16MB (new maximum)
        (16777217, False),                  # Over maximum
        (20971520, False),                  # 20MB (too large)
        (-1, False),                        # Negative value
    ]
)
def test_zvol_special_small_block_size_validation(value, valid):
    """
    Test that special_small_block_size validation accepts 0-16MB range (ZFS 2.4).
    Previously limited to 512B-1MB and required power of 2.
    """
    zvol_name = f'test_zvol_validation_{value}'  # dataset() adds pool prefix automatically

    if valid:
        with dataset(zvol_name, {
            'type': 'VOLUME',
            'volsize': _1GiB,
            'volblocksize': '128K',
            'special_small_block_size': value
        }) as zvol:
            zvol_info = call('pool.dataset.get_instance', zvol)
            assert zvol_info['special_small_block_size']['value'] == str(value)
    else:
        with pytest.raises(ValidationErrors):
            dataset_obj = dataset(zvol_name, {
                'type': 'VOLUME',
                'volsize': _1GiB,
                'volblocksize': '128K',
                'special_small_block_size': value
            })
            with dataset_obj:
                pass


def test_zvol_non_power_of_two_special_small_block_size():
    """
    Test that non-power-of-2 values are now accepted for special_small_block_size (ZFS 2.4).
    Previously required power of 2 values only.
    """
    non_power_of_two_values = [
        3145728,   # 3MB (not power of 2)
        5242880,   # 5MB (not power of 2)
        10485760,  # 10MB (not power of 2)
    ]

    for value in non_power_of_two_values:
        zvol_name = f'test_zvol_non_pow2_{value}'
        with dataset(zvol_name, {
            'type': 'VOLUME',
            'volsize': _1GiB,
            'volblocksize': '128K',
            'special_small_block_size': value
        }) as zvol:
            zvol_info = call('pool.dataset.get_instance', zvol)
            assert zvol_info['special_small_block_size']['value'] == str(value)


def test_zvol_inherit_from_parent_dataset():
    """
    Test zvol inheriting special_small_block_size from parent dataset.
    This is valid when volblocksize >= parent threshold.
    """
    # Create parent with threshold = 64K
    with dataset('test_inherit_parent', {
        'type': 'FILESYSTEM',
        'special_small_block_size': 65536  # 64K
    }) as parent:
        # Create zvol with volblocksize=128K (larger than 64K)
        zvol_name = f'{parent}/zvol_inherit'
        zvol = call('pool.dataset.create', {
            'name': zvol_name,
            'type': 'VOLUME',
            'volsize': _1GiB,
            'volblocksize': '128K',  # 128K > 64K, safe to inherit
            'special_small_block_size': 'INHERIT'
        })

        try:
            # Should inherit parent's value or show as INHERIT
            zvol_check = call('pool.dataset.get_instance', zvol_name)
            # Can be INHERIT or the inherited numeric value
            special_value = zvol_check['special_small_block_size']['value']
            assert special_value in ('INHERIT', '65536')
        finally:
            call('pool.dataset.delete', zvol_name)


def test_zvol_update_special_small_block_size():
    """
    Test that special_small_block_size can be updated on existing zvols.
    """
    with dataset('test_zvol_update', {
        'type': 'VOLUME',
        'volsize': _1GiB,
        'volblocksize': '128K',
        'special_small_block_size': 0  # Initially disabled
    }) as zvol:
        zvol_info = call('pool.dataset.get_instance', zvol)
        assert zvol_info['special_small_block_size']['value'] == '0'

        # Update to enable special vdev usage
        updated = call('pool.dataset.update', zvol, {
            'special_small_block_size': 1048576  # 1MB
        })

        assert updated['special_small_block_size']['value'] == '1048576'


def test_zvol_special_small_block_size_set_to_zero():
    """
    Test that setting special_small_block_size=0 disables special vdev usage for zvol.
    """
    with dataset('test_zvol_zero', {
        'type': 'VOLUME',
        'volsize': _1GiB,
        'volblocksize': '128K',
        'special_small_block_size': 0
    }) as zvol:
        zvol_info = call('pool.dataset.get_instance', zvol)
        assert zvol_info['special_small_block_size']['value'] == '0'
        # With value=0, all blocks go to data vdevs (special vdev disabled)


@pytest.mark.parametrize(
    'parent_threshold,volblocksize,should_auto_protect', [
        (1048576, '128K', True),    # 1MB > 128K → auto-protect
        (1048576, '64K', True),     # 1MB > 64K → auto-protect
        (131072, '128K', False),    # 128K = 128K → no protection needed (equal)
        (65536, '128K', False),     # 64K < 128K → no protection needed
        (2097152, '16K', True),     # 2MB > 16K → auto-protect
        (16384, '64K', False),      # 16K < 64K → no protection needed
    ]
)
def test_zvol_auto_protection_scenarios(parent_threshold, volblocksize, should_auto_protect):
    """
    Parametrized test for various combinations of parent threshold and zvol volblocksize.
    Tests the auto-protection logic comprehensively.
    """
    with dataset('test_auto_protect_parent', {
        'type': 'FILESYSTEM',
        'special_small_block_size': parent_threshold
    }) as parent:
        zvol_name = f'{parent}/zvol_{volblocksize}'
        zvol = call('pool.dataset.create', {
            'name': zvol_name,
            'type': 'VOLUME',
            'volsize': _1GiB,
            'volblocksize': volblocksize
        })

        try:
            zvol_check = call('pool.dataset.get_instance', zvol_name)
            special_value = zvol_check['special_small_block_size']['value']

            if should_auto_protect:
                # Should be auto-set to 0
                assert special_value == '0', \
                    f'Expected auto-protection (0) for volblocksize={volblocksize} < parent={parent_threshold}'
            else:
                # Should inherit or be INHERIT
                assert special_value in ('INHERIT', str(parent_threshold)), \
                    f'Should allow inheritance for volblocksize={volblocksize} >= parent={parent_threshold}'
        finally:
            call('pool.dataset.delete', zvol_name)


def test_zvol_parent_special_zero_no_auto_protection():
    """
    Test that when parent has special_small_block_size=0 (disabled),
    no auto-protection is needed for child zvol.
    """
    with dataset('test_parent_zero', {
        'type': 'FILESYSTEM',
        'special_small_block_size': 0  # Disabled
    }) as parent:
        zvol_name = f'{parent}/zvol_parent_zero'
        zvol = call('pool.dataset.create', {
            'name': zvol_name,
            'type': 'VOLUME',
            'volsize': _1GiB,
            'volblocksize': '64K'
        })

        try:
            # No auto-protection needed (parent has it disabled)
            zvol_check = call('pool.dataset.get_instance', zvol_name)
            # Should inherit 0 or be INHERIT
            assert zvol_check['special_small_block_size']['value'] in ('0', 'INHERIT')
        finally:
            call('pool.dataset.delete', zvol_name)


def test_zvol_maximum_special_small_block_size():
    """
    Test that zvols can use the maximum special_small_block_size value (16MB).
    """
    with dataset('test_zvol_max', {
        'type': 'VOLUME',
        'volsize': _1GiB,
        'volblocksize': '128K',
        'special_small_block_size': 16777216  # 16MB (maximum)
    }) as zvol:
        zvol_info = call('pool.dataset.get_instance', zvol)
        assert zvol_info['special_small_block_size']['value'] == '16777216'


def test_zvol_special_small_block_size_inherit_string():
    """
    Test that 'INHERIT' string value works correctly for zvols.
    """
    with dataset('test_zvol_inherit_str', {
        'type': 'VOLUME',
        'volsize': _1GiB,
        'volblocksize': '128K',
        'special_small_block_size': 'INHERIT'
    }) as zvol:
        zvol_info = call('pool.dataset.get_instance', zvol)
        # Should be INHERIT or inherited value
        assert zvol_info['special_small_block_size']['value'] in ('INHERIT', '0')
