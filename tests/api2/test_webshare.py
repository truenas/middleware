import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool


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
            path1 = f'/mnt/{ds1}'

            # Datasets automatically create their mount point directories
            # No need to create them manually

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
            # Dataset automatically creates its mount point directory

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

    def test_service_auto_selects_pool_on_manual_start(self):
        """Test that service auto-selects pools when manually started."""
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

                # Starting the service should auto-select pools
                call('service.start', 'webshare', {})

                # Check that pools were auto-selected
                config = call('webshare.config')
                assert config['bulk_download_pool'] is not None
                assert config['search_index_pool'] is not None

        finally:
            # Restore original state
            if not service_status['enable']:
                call('service.update', 'webshare', {'enable': False})
                # Service might be running now, stop it
                try:
                    call('service.stop', 'webshare', {})
                except Exception:
                    pass

            call('webshare.update', {
                'bulk_download_pool':
                    original_config['bulk_download_pool'],
                'search_index_pool':
                    original_config['search_index_pool']
            })

    def test_service_auto_configuration_sets_permissions(self):
        """Test auto-configuration sets correct permissions on datasets."""
        original_config = call('webshare.config')

        try:
            # Clear pool configuration
            call('webshare.update', {
                'bulk_download_pool': None,
                'search_index_pool': None,
                'search_enabled': True  # Enable search to test permissions
            })

            # Call check_configuration which should auto-configure pools
            call('service.start', 'webshare')

            # Get the updated configuration
            config = call('webshare.config')
            assert config['bulk_download_pool'] is not None
            assert config['search_index_pool'] is not None

            # Check bulk download dataset permissions (should be 777)
            bulk_dataset = (f"{config['bulk_download_pool']}/"
                            ".webshare-private/bulk_download")
            datasets = call('zfs.dataset.query',
                            [['name', '=', bulk_dataset]])
            assert len(datasets) == 1

            bulk_mount = datasets[0]['properties']['mountpoint']['value']
            bulk_stat = call('filesystem.stat', bulk_mount)
            # Check permissions are 777 (octal 0o777 = decimal 511)
            assert bulk_stat['mode'] & 0o777 == 0o777, \
                f"Expected mode 777, got {oct(bulk_stat['mode'] & 0o777)}"

            # Check search index dataset ownership (truesearch:truesearch)
            search_dataset = (f"{config['search_index_pool']}/"
                              ".webshare-private/search-index")
            datasets = call('zfs.dataset.query',
                            [['name', '=', search_dataset]])
            assert len(datasets) == 1

            search_mount = datasets[0]['properties']['mountpoint']['value']
            search_stat = call('filesystem.stat', search_mount)

            # Get truesearch user/group info
            truesearch_user = call('user.query',
                                   [['username', '=', 'truesearch']],
                                   {'get': True})
            truesearch_group = call('group.query',
                                    [['group', '=', 'truesearch']],
                                    {'get': True})

            assert search_stat['uid'] == truesearch_user['uid'], \
                f"Expected uid {truesearch_user['uid']}, " \
                f"got {search_stat['uid']}"
            assert search_stat['gid'] == truesearch_group['gid'], \
                f"Expected gid {truesearch_group['gid']}, " \
                f"got {search_stat['gid']}"

            # Stop the service
            call('service.stop', 'webshare')

        finally:
            # Restore original configuration
            call('webshare.update', {
                'bulk_download_pool': original_config['bulk_download_pool'],
                'search_index_pool': original_config['search_index_pool'],
                'search_enabled': original_config['search_enabled']
            })

    def test_service_with_search_enabled(self):
        """Test WebShare service with search functionality enabled."""
        original_config = call('webshare.config')

        with dataset('webshare_search_dir') as ds:
            search_path = f'/mnt/{ds}'
            # Dataset automatically creates its mount point directory

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
