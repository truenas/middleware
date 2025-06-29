import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool
from truenas_api_client import ClientException


# Skip all tests if no pool is available
pytestmark = pytest.mark.skipif(
    pool is None,
    reason="WebShare tests require a pool to be configured"
)


class TestWebshareConfig:
    """Test WebShare configuration API endpoints."""

    def test_config_returns_default_values(self):
        """Test that webshare.config returns expected default configuration."""
        config = call('webshare.config')

        assert config['id'] == 1
        assert config['truenas_host'] == 'localhost'
        assert config['log_level'] == 'info'
        assert config['session_log_retention'] == 20
        assert config['enable_web_terminal'] is False
        assert config['search_enabled'] is False
        assert isinstance(config['altroots'], dict)
        assert isinstance(config['search_directories'], list)

    def test_update_basic_settings(self):
        """Test updating basic WebShare settings."""
        original_config = call('webshare.config')

        try:
            # Update basic settings
            updated = call('webshare.update', {
                'truenas_host': 'test.local',
                'log_level': 'debug',
                'session_log_retention': 30,
                'enable_web_terminal': True
            })

            assert updated['truenas_host'] == 'test.local'
            assert updated['log_level'] == 'debug'
            assert updated['session_log_retention'] == 30
            assert updated['enable_web_terminal'] is True

        finally:
            # Restore original settings
            call('webshare.update', {
                'truenas_host': original_config['truenas_host'],
                'log_level': original_config['log_level'],
                'session_log_retention':
                    original_config['session_log_retention'],
                'enable_web_terminal': original_config['enable_web_terminal']
            })


class TestWebshareValidation:
    """Test WebShare configuration validation."""

    def test_validate_invalid_pool(self):
        """Test validation rejects invalid pool names."""
        with pytest.raises(ValidationErrors) as exc_info:
            call('webshare.validate', {
                'bulk_download_pool': 'nonexistent_pool'
            })
        assert 'not a valid imported pool' in str(exc_info.value)

    def test_validate_boot_pool_rejected(self):
        """Test validation rejects boot pool."""
        boot_pool = call('boot.pool_name')

        # Skip test if no boot pool (some test environments)
        if not boot_pool:
            pytest.skip("No boot pool available in test environment")

        with pytest.raises(ValidationErrors) as exc_info:
            call('webshare.validate', {
                'search_index_pool': boot_pool
            })
        assert 'not a valid imported pool' in str(exc_info.value)

    def test_validate_altroots_duplicate_values(self):
        """Test validation rejects duplicate values in altroots."""
        with dataset('webshare_test1') as ds1:
            with dataset('webshare_test2') as ds2:
                path1 = f'/mnt/{ds1}'
                path2 = f'/mnt/{ds2}'

                # Create the directories (ignore if they already exist)
                try:
                    call('filesystem.mkdir', {'path': path1})
                except ClientException as e:
                    if 'path already exists' not in str(e):
                        raise
                try:
                    call('filesystem.mkdir', {'path': path2})
                except ClientException as e:
                    if 'path already exists' not in str(e):
                        raise

                with pytest.raises(ValidationErrors) as exc_info:
                    call('webshare.validate', {
                        'altroots': {
                            'root1': path1,
                            'root2': path1  # Duplicate value
                        }
                    })
                assert 'Duplicate values are not allowed' in \
                    str(exc_info.value)

    def test_validate_altroots_invalid_path(self):
        """Test validation rejects paths not under /mnt/."""
        with pytest.raises(ValidationErrors) as exc_info:
            call('webshare.validate', {
                'altroots': {
                    'invalid': '/tmp/test'
                }
            })
        assert 'Path must be under /mnt/<poolname>/' in str(exc_info.value)

    def test_validate_altroots_nonexistent_path(self):
        """Test validation rejects nonexistent paths."""
        with pytest.raises(ValidationErrors) as exc_info:
            call('webshare.validate', {
                'altroots': {
                    'missing': f'/mnt/{pool}/nonexistent_directory'
                }
            })
        assert 'Path does not exist or is not accessible' in \
            str(exc_info.value)

    def test_validate_search_directories(self):
        """Test validation of search directories."""
        with dataset('webshare_search_test') as ds:
            path = f'/mnt/{ds}'
            try:
                call('filesystem.mkdir', {'path': path})
            except ClientException as e:
                if 'path already exists' not in str(e):
                    raise

            # Valid path should pass
            call('webshare.validate', {
                'search_directories': [path]
            })

            # Invalid path should fail
            with pytest.raises(ValidationErrors) as exc_info:
                call('webshare.validate', {
                    'search_directories': ['/invalid/path']
                })
            assert 'Path must be under /mnt/<poolname>/' in str(exc_info.value)

    def test_validate_time_format(self):
        """Test validation of pruning start time format."""
        # Valid time formats
        for valid_time in ['00:00', '12:30', '23:59']:
            call('webshare.validate', {
                'search_pruning_start_time': valid_time
            })

        # Invalid time formats
        for invalid_time in ['24:00', '12:60', 'invalid', '1:30', '12:3']:
            with pytest.raises(ValidationErrors) as exc_info:
                call('webshare.validate', {
                    'search_pruning_start_time': invalid_time
                })
            assert 'Invalid time format. Use HH:MM (24-hour format)' in \
                str(exc_info.value)

    def test_validate_cleanup_threshold_range(self):
        """Test validation of cleanup threshold percentage."""
        # Valid range
        for valid_value in [0, 50, 100]:
            call('webshare.validate', {
                'search_index_cleanup_threshold': valid_value
            })

        # Invalid range
        for invalid_value in [-1, 101, 200]:
            with pytest.raises(ValidationErrors) as exc_info:
                call('webshare.validate', {
                    'search_index_cleanup_threshold': invalid_value
                })
            assert 'Threshold must be between 0 and 100 (percentage)' in \
                str(exc_info.value)


class TestWebshareDatasets:
    """Test WebShare dataset management."""

    def test_dataset_creation_with_pools(self):
        """Test that datasets are created when pools are configured."""
        original_config = call('webshare.config')

        try:
            # Update with pool configuration
            call('webshare.update', {
                'bulk_download_pool': pool,
                'search_index_pool': pool
            })

            # Check that datasets were created
            bulk_dataset = f'{pool}/.webshare-private/bulk_download'
            search_dataset = f'{pool}/.webshare-private/search-index'

            datasets = call('zfs.dataset.query', [
                ['name', 'in', [bulk_dataset, search_dataset]]
            ])
            dataset_names = [ds['name'] for ds in datasets]

            assert bulk_dataset in dataset_names
            assert search_dataset in dataset_names

            # Check mount points (should be at default ZFS location)
            for ds in datasets:
                mountpoint = ds['properties']['mountpoint']['value']
                if ds['name'] == bulk_dataset:
                    expected_mount = (f'/mnt/{pool}/.webshare-private/'
                                      'bulk_download')
                    assert mountpoint == expected_mount, \
                        f"Expected {expected_mount}, got {mountpoint}"
                elif ds['name'] == search_dataset:
                    expected_mount = (f'/mnt/{pool}/.webshare-private/'
                                      'search-index')
                    assert mountpoint == expected_mount, \
                        f"Expected {expected_mount}, got {mountpoint}"

        finally:
            # Restore original configuration
            call('webshare.update', {
                'bulk_download_pool':
                    original_config['bulk_download_pool'],
                'search_index_pool':
                    original_config['search_index_pool']
            })

    def test_dataset_removal_on_pool_change(self):
        """Test that datasets are removed when pool is changed."""
        original_config = call('webshare.config')

        try:
            # First set a pool
            call('webshare.update', {
                'bulk_download_pool': pool
            })

            # Verify dataset exists
            dataset_name = f'{pool}/.webshare-private/bulk_download'
            datasets = call('zfs.dataset.query', [['name', '=', dataset_name]])
            assert len(datasets) == 1

            # Change to no pool
            call('webshare.update', {
                'bulk_download_pool': None
            })

            # Verify dataset was removed
            datasets = call('zfs.dataset.query', [['name', '=', dataset_name]])
            assert len(datasets) == 0

        finally:
            # Restore original configuration
            call('webshare.update', {
                'bulk_download_pool':
                    original_config['bulk_download_pool']
            })


class TestWebshareService:
    """Test WebShare service operations."""

    def test_service_requires_pool_configuration(self):
        """Test that service requires pools to be configured before starting."""
        original_config = call('webshare.config')
        service_status = call('service.query',
                              [['service', '=', 'webshare']],
                              {'get': True})

        try:
            # Clear pool configuration
            call('webshare.update', {
                'bulk_download_pool': None,
                'search_index_pool': None
            })

            # Try to start the service without pools configured
            if not service_status['enable']:
                call('service.update', 'webshare', {'enable': True})
                
                # Starting the service should fail
                with pytest.raises(CallError) as exc_info:
                    call('service.start', 'webshare')
                
                # Check that the error mentions pool configuration
                assert 'No bulk download pool configured' in str(exc_info.value)

        finally:
            # Restore original state
            if not service_status['enable']:
                call('service.update', 'webshare', {'enable': False})
                # Service might not be running, so ignore stop errors
                try:
                    call('service.stop', 'webshare')
                except Exception:
                    pass

            call('webshare.update', {
                'bulk_download_pool':
                    original_config['bulk_download_pool'],
                'search_index_pool':
                    original_config['search_index_pool']
            })

    def test_service_with_search_enabled(self):
        """Test WebShare service with search functionality enabled."""
        original_config = call('webshare.config')

        with dataset('webshare_search_dir') as ds:
            search_path = f'/mnt/{ds}'
            try:
                call('filesystem.mkdir', {'path': search_path})
            except ClientException as e:
                if 'path already exists' not in str(e):
                    raise

            try:
                # Configure with search enabled
                call('webshare.update', {
                    'search_index_pool': pool,
                    'search_enabled': True,
                    'search_directories': [search_path],
                    'search_pruning_enabled': True,
                    'search_pruning_schedule': 'daily',
                    'search_pruning_start_time': '02:00'
                })

                # Verify configuration was applied
                config = call('webshare.config')
                assert config['search_enabled'] is True
                assert search_path in config['search_directories']

                # Verify search configuration file would be generated
                # (The actual file generation happens in before_start)

            finally:
                # Restore original configuration
                call('webshare.update', {
                    'search_index_pool':
                        original_config['search_index_pool'],
                    'search_enabled': original_config['search_enabled'],
                    'search_directories':
                        original_config['search_directories'],
                    'search_pruning_enabled':
                        original_config['search_pruning_enabled'],
                    'search_pruning_schedule':
                        original_config['search_pruning_schedule'],
                    'search_pruning_start_time':
                        original_config['search_pruning_start_time']
                })
