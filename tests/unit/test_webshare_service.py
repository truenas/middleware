import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middlewared.plugins.webshare import WebShareService


class TestWebShareValidation:
    """Test WebShare validation logic."""

    @pytest.mark.asyncio
    async def test_validate_pool_path_valid(self):
        """Test validation accepts valid pool paths."""
        service = WebShareService(None)
        service.middleware = AsyncMock()

        # Mock filesystem.stat to indicate path exists
        service.middleware.call = AsyncMock(return_value={'mode': 16877})

        verrors = MagicMock()
        verrors.add = MagicMock()

        pool_names = ['tank', 'storage']

        # Valid path under pool
        await service._validate_pool_path(
            verrors, 'field', 'name', '/mnt/tank/share', pool_names
        )

        verrors.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_pool_path_not_under_mnt(self):
        """Test validation rejects paths not under /mnt/."""
        service = WebShareService(None)

        verrors = MagicMock()
        verrors.add = MagicMock()

        pool_names = ['tank']

        await service._validate_pool_path(
            verrors, 'field', 'name', '/tmp/invalid', pool_names
        )

        verrors.add.assert_called_once()
        args = verrors.add.call_args[0]
        assert args[0] == 'field.name'
        assert 'Path must be under /mnt/' in args[1]

    @pytest.mark.asyncio
    async def test_validate_pool_path_invalid_pool(self):
        """Test validation rejects paths under non-existent pools."""
        service = WebShareService(None)

        verrors = MagicMock()
        verrors.add = MagicMock()

        pool_names = ['tank']

        await service._validate_pool_path(
            verrors, 'field', 'name', '/mnt/invalid_pool/share', pool_names
        )

        verrors.add.assert_called_once()
        args = verrors.add.call_args[0]
        assert args[0] == 'field.name'
        assert 'Path must be under a valid pool' in args[1]

    @pytest.mark.asyncio
    async def test_validate_altroots_duplicate_values(self):
        """Test validation detects duplicate values in altroots."""
        service = WebShareService(None)
        service.middleware = AsyncMock()

        # Mock pool query
        service.middleware.call = AsyncMock()
        service.middleware.call.side_effect = [
            'boot-pool',  # boot.pool_name
            [{'name': 'tank', 'status': 'ONLINE'}],  # pool.query
        ]

        verrors = MagicMock()
        verrors.add = MagicMock()
        verrors.check = MagicMock()

        data = {
            'altroots': {
                'root1': '/mnt/tank/share1',
                'root2': '/mnt/tank/share1'  # Duplicate value
            }
        }

        await service._validate(data)

        verrors.add.assert_called()
        args = verrors.add.call_args[0]
        assert args[0] == 'webshare_update.altroots'
        assert 'Duplicate values' in args[1]

    @pytest.mark.asyncio
    async def test_validate_time_format(self):
        """Test time format validation."""
        service = WebShareService(None)
        service.middleware = AsyncMock()

        # Mock pool query
        service.middleware.call = AsyncMock()
        service.middleware.call.side_effect = [
            'boot-pool',  # boot.pool_name
            [{'name': 'tank', 'status': 'ONLINE'}],  # pool.query
        ]

        verrors = MagicMock()
        verrors.add = MagicMock()
        verrors.check = MagicMock()

        # Valid time
        data = {'search_pruning_start_time': '14:30'}
        await service._validate(data)
        verrors.add.assert_not_called()

        # Invalid time - hour out of range
        verrors.reset_mock()
        data = {'search_pruning_start_time': '25:00'}
        await service._validate(data)
        verrors.add.assert_called()
        assert 'Invalid time format' in verrors.add.call_args[0][1]

        # Invalid time - minute out of range
        verrors.reset_mock()
        data = {'search_pruning_start_time': '12:60'}
        await service._validate(data)
        verrors.add.assert_called()
        assert 'Invalid time format' in verrors.add.call_args[0][1]


class TestWebShareConfigGeneration:
    """Test configuration file generation."""

    @pytest.mark.asyncio
    async def test_generate_auth_config(self):
        """Test generation of webshare-auth configuration."""
        service = WebShareService(None)
        service.middleware = AsyncMock()

        config = {
            'truenas_host': 'nas.local',
            'log_level': 'debug',
            'session_log_retention': 25,
            'enable_web_terminal': True,
            'bulk_download_pool': 'tank',
            'search_enabled': True
        }

        service.config = AsyncMock(return_value=config)

        with tempfile.TemporaryDirectory():
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file

                with patch('pathlib.Path.mkdir'):
                    await service._generate_config_files()

                # Check that auth config was written
                mock_open.assert_any_call(
                    '/etc/webshare-auth/config.json', 'w'
                )

                # Verify the config content
                written_calls = [
                    call for call in mock_file.method_calls
                    if call[0] == 'write'
                ]
                if written_calls:
                    # json.dump was used
                    pass
                else:
                    # Check json.dump calls
                    import json as json_module
                    with patch.object(json_module, 'dump') as mock_dump:
                        with patch('pathlib.Path.mkdir'):
                            await service._generate_config_files()

                        auth_config_call = mock_dump.call_args_list[0]
                        auth_config = auth_config_call[0][0]

                        assert auth_config['truenashost'] == 'nas.local'
                        assert auth_config['log_level'] == 'debug'
                        assert auth_config['session_log_retention'] == 25
                        assert auth_config['enable_web_terminal'] is True
                        bulk_dl_tmp = '/var/cache/webshare/bulk_download'
                        assert auth_config['bulk_download_tmp'] == bulk_dl_tmp
                        assert auth_config['truesearch']['enabled'] is True

    @pytest.mark.asyncio
    async def test_generate_search_config_with_altroots_metadata(self):
        """Test search config generation includes altroots with indexed."""
        service = WebShareService(None)
        service.middleware = AsyncMock()

        config = {
            'search_enabled': True,
            'search_directories': ['/mnt/tank/docs'],
            'altroots': {
                'media': '/mnt/tank/media',
                'private': '/mnt/tank/private',
                'public': '/mnt/tank/public'
            },
            'altroots_metadata': {
                'media': {'search_indexed': True},
                'private': {'search_indexed': False},
                'public': {}  # Defaults to True
            },
            'search_index_pool': 'tank',
            'log_level': 'info',
            'search_max_file_size': 104857600,
            'search_supported_types': ['document', 'text'],
            'search_worker_count': 4,
            'search_archive_enabled': True,
            'search_archive_max_depth': 2,
            'search_archive_max_size': 524288000,
            'search_index_max_size': 10737418240,
            'search_index_cleanup_enabled': True,
            'search_index_cleanup_threshold': 90,
            'search_pruning_enabled': True,
            'search_pruning_schedule': 'daily',
            'search_pruning_start_time': '02:00'
        }

        service.config = AsyncMock(return_value=config)

        with patch('builtins.open', create=True):
            with patch('json.dump') as mock_dump:
                with patch('pathlib.Path.mkdir'):
                    await service._generate_config_files()

                # Find the truesearch config dump call
                search_config_call = None
                for call in mock_dump.call_args_list:
                    if (len(call[0]) > 1 and
                            hasattr(call[0][1], 'name') and
                            '/etc/truesearch/config.json' in
                            str(call[0][1].name)):
                        search_config_call = call
                        break

                assert search_config_call is not None
                search_config = search_config_call[0][0]

                # Verify directories include docs, media, and public
                # but not private
                assert '/mnt/tank/docs' in search_config['directories']
                assert '/mnt/tank/media' in search_config['directories']
                assert '/mnt/tank/public' in search_config['directories']
                assert '/mnt/tank/private' not in search_config['directories']
                assert len(search_config['directories']) == 3


class TestWebShareDatasetManagement:
    """Test dataset creation and management."""

    @pytest.mark.asyncio
    async def test_update_datasets_creates_new(self):
        """Test dataset creation when pools are configured."""
        service = WebShareService(None)
        service.middleware = AsyncMock()

        old_config = {
            'bulk_download_pool': None,
            'search_index_pool': None
        }

        new_config = {
            'bulk_download_pool': 'tank',
            'search_index_pool': 'tank'
        }

        # Mock ZFS operations
        service.middleware.call = AsyncMock()
        service.middleware.call.side_effect = [
            [],  # Parent dataset doesn't exist
            None,  # Create parent dataset
            [],  # Bulk download dataset doesn't exist
            None,  # Create bulk download dataset
            [],  # Search index dataset doesn't exist
            None,  # Create search index dataset
        ]

        with patch('os.makedirs'):
            await service._update_datasets(old_config, new_config)

        # Verify dataset creation calls
        calls = service.middleware.call.call_args_list

        # Check parent dataset creation
        assert any(
            call[0][0] == 'zfs.dataset.create' and
            call[0][1]['name'] == 'tank/.webshare-private'
            for call in calls
        )

        # Check bulk download dataset creation
        assert any(
            call[0][0] == 'zfs.dataset.create' and
            call[0][1]['name'] == 'tank/.webshare-private/bulk_download' and
            call[0][1]['properties']['mountpoint'] == 'legacy'
            for call in calls
        )

        # Check search index dataset creation
        assert any(
            call[0][0] == 'zfs.dataset.create' and
            call[0][1]['name'] == 'tank/.webshare-private/search-index' and
            call[0][1]['properties']['mountpoint'] == 'legacy'
            for call in calls
        )

    @pytest.mark.asyncio
    async def test_update_datasets_removes_old(self):
        """Test dataset removal when pool is changed."""
        service = WebShareService(None)
        service.middleware = AsyncMock()

        old_config = {
            'bulk_download_pool': 'oldpool',
            'search_index_pool': 'oldpool'
        }

        new_config = {
            'bulk_download_pool': 'newpool',
            'search_index_pool': 'newpool'
        }

        # Mock ZFS operations
        service.middleware.call = AsyncMock()
        service.middleware.call.side_effect = [
            # Old dataset exists
            [{'name': 'oldpool/.webshare-private/bulk_download'}],
            None,  # Delete old dataset
            # Old dataset exists
            [{'name': 'oldpool/.webshare-private/search-index'}],
            None,  # Delete old dataset
            [],  # New parent doesn't exist
            None,  # Create new parent
            [],  # New bulk dataset doesn't exist
            None,  # Create new bulk dataset
            [],  # New search dataset doesn't exist
            None,  # Create new search dataset
        ]

        with patch('os.makedirs'):
            await service._update_datasets(old_config, new_config)

        # Verify old dataset deletion calls
        calls = service.middleware.call.call_args_list

        assert any(
            call[0][0] == 'zfs.dataset.delete' and
            call[0][1] == 'oldpool/.webshare-private/bulk_download'
            for call in calls
        )

        assert any(
            call[0][0] == 'zfs.dataset.delete' and
            call[0][1] == 'oldpool/.webshare-private/search-index'
            for call in calls
        )

    @pytest.mark.asyncio
    async def test_mount_datasets(self):
        """Test dataset mounting functionality."""
        service = WebShareService(None)
        service.middleware = AsyncMock()

        config = {
            'bulk_download_pool': 'tank',
            'search_index_pool': 'tank'
        }

        service.config = AsyncMock(return_value=config)

        # Mock ZFS dataset query and filesystem operations
        service.middleware.call = AsyncMock()
        service.middleware.call.side_effect = [
            # bulk dataset exists
            [{'name': 'tank/.webshare-private/bulk_download'}],
            [],  # bulk not mounted
            None,  # mount bulk dataset
            # search dataset exists
            [{'name': 'tank/.webshare-private/search-index'}],
            [],  # search not mounted
            None,  # mount search dataset
        ]

        with patch('os.makedirs') as mock_makedirs:
            await service._mount_datasets()

            # Verify mount directories were created
            mock_makedirs.assert_any_call(
                '/var/cache/webshare/bulk_download', exist_ok=True
            )
            mock_makedirs.assert_any_call(
                '/var/cache/webshare/index', exist_ok=True
            )

            # Verify mount calls
            calls = service.middleware.call.call_args_list
            mount_calls = [
                call for call in calls if call[0][0] == 'filesystem.mount'
            ]

            assert len(mount_calls) == 2

            # Check bulk download mount
            bulk_mount = next(
                call for call in mount_calls
                if call[0][1]['path'] == '/var/cache/webshare/bulk_download'
            )
            assert bulk_mount[0][1]['fs_type'] == 'zfs'
            assert (bulk_mount[0][1]['fs_path'] ==
                    'tank/.webshare-private/bulk_download')

            # Check search index mount
            search_mount = next(
                call for call in mount_calls
                if call[0][1]['path'] == '/var/cache/webshare/index'
            )
            assert search_mount[0][1]['fs_type'] == 'zfs'
            assert (search_mount[0][1]['fs_path'] ==
                    'tank/.webshare-private/search-index')


class TestWebSharePermissions:
    """Test directory permission management."""

    @pytest.mark.asyncio
    async def test_set_directory_permissions(self):
        """Test setting proper ownership and permissions."""
        service = WebShareService(None)
        service.middleware = AsyncMock()

        with patch('os.path.exists') as mock_exists:
            # Both directories exist
            mock_exists.side_effect = [True, True]

            with patch('pwd.getpwnam') as mock_getpwnam:
                mock_getpwnam.return_value.pw_uid = 1001

                with patch('grp.getgrnam') as mock_getgrnam:
                    mock_getgrnam.return_value.gr_gid = 1001

                    with patch('os.chown') as mock_chown:
                        with patch('os.chmod') as mock_chmod:
                            with patch('os.walk') as mock_walk:
                                mock_walk.return_value = []

                                await service._set_directory_permissions()

                                # Verify truesearch user lookup
                                mock_getpwnam.assert_called_with('truesearch')
                                mock_getgrnam.assert_called_with('truesearch')

                                # Verify ownership change for index directory
                                mock_chown.assert_called_with(
                                    '/var/cache/webshare/index', 1001, 1001
                                )

                                # Verify permissions for bulk download dir
                                mock_chmod.assert_called_with(
                                    '/var/cache/webshare/bulk_download',
                                    0o777
                                )
