import json
import pathlib

import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    WebShareEntry, WebShareUpdateArgs, WebShareUpdateResult,
    WebShareValidateArgs, WebShareValidateResult
)
from middlewared.schema import ValidationErrors
from middlewared.service import CallError, SystemServiceService, private


class WebShareModel(sa.Model):
    __tablename__ = 'services_webshare'

    id = sa.Column(sa.Integer(), primary_key=True)
    srv_truenas_host = sa.Column(sa.String(255), default='localhost')
    srv_log_level = sa.Column(sa.String(20), default='info')
    srv_pam_service_name = sa.Column(sa.String(50), default='webshare')
    srv_allowed_groups = sa.Column(sa.JSON(list), default=['webshare'])
    srv_session_log_retention = sa.Column(sa.Integer(), default=20)
    srv_enable_web_terminal = sa.Column(sa.Boolean(), default=False)
    srv_bulk_download_pool = sa.Column(sa.String(255), nullable=True)
    srv_search_index_pool = sa.Column(sa.String(255), nullable=True)
    srv_altroots = sa.Column(sa.JSON(dict), default={})
    srv_altroots_metadata = sa.Column(sa.JSON(dict), default={})
    srv_search_enabled = sa.Column(sa.Boolean(), default=False)
    srv_search_directories = sa.Column(sa.JSON(list), default=[])
    srv_search_max_file_size = sa.Column(sa.Integer(), default=104857600)
    srv_search_supported_types = sa.Column(
        sa.JSON(list),
        default=['image', 'audio', 'video', 'document', 'archive', 'text',
                 'disk_image']
    )
    srv_search_worker_count = sa.Column(sa.Integer(), default=4)
    srv_search_archive_enabled = sa.Column(sa.Boolean(), default=True)
    srv_search_archive_max_depth = sa.Column(sa.Integer(), default=2)
    srv_search_archive_max_size = sa.Column(sa.Integer(), default=524288000)
    srv_search_index_max_size = sa.Column(sa.Integer(), default=10737418240)
    srv_search_index_cleanup_enabled = sa.Column(sa.Boolean(), default=True)
    srv_search_index_cleanup_threshold = sa.Column(
        sa.Integer(), default=90  # Stored as percentage
    )
    srv_search_pruning_enabled = sa.Column(sa.Boolean(), default=False)
    srv_search_pruning_schedule = sa.Column(sa.String(20), default='daily')
    srv_search_pruning_start_time = sa.Column(sa.String(10), default='23:00')


class WebShareService(SystemServiceService):

    class Config:
        datastore = 'services.webshare'
        service = 'webshare'
        datastore_prefix = 'srv_'
        cli_namespace = 'service.webshare'
        role_prefix = 'SHARING'
        entry = WebShareEntry

    async def config(self):
        """Get WebShare configuration with proper defaults."""
        config = await super().config()

        # Ensure pam_service_name is always 'webshare'
        config['pam_service_name'] = 'webshare'

        # Ensure allowed_groups defaults to ['webshare'] if empty
        if not config.get('allowed_groups'):
            config['allowed_groups'] = ['webshare']

        return config

    @api_method(WebShareValidateArgs, WebShareValidateResult,
                roles=['SHARING_READ'])
    async def validate(self, data):
        """
        Validate WebShare configuration without saving.
        """
        config = await self.config()
        config.update(data)
        await self._validate(config)

    @api_method(
        WebShareUpdateArgs, WebShareUpdateResult,
        audit='Update WebShare configuration', roles=['SHARING_WRITE']
    )
    async def do_update(self, data):
        """
        Update WebShare service configuration.

        `truenas_host` specifies the TrueNAS API endpoint for authentication.

        `bulk_download_pool` and `search_index_pool` must be valid imported
        pools. The service will automatically create datasets under
        <pool>/.webshare-private/ for these features.

        `altroots` defines alternative root paths for file access. Keys and
        values must be unique, and paths must be under /mnt/<poolname>/.

        `search_directories` lists directories to index, which must also be
        under /mnt/<poolname>/.
        """
        old = await self.config()
        new = old.copy()
        new.update(data)

        # Ensure pam_service_name is always 'webshare' (read-only field)
        new['pam_service_name'] = 'webshare'

        # Ensure allowed_groups defaults to ['webshare'] if empty
        if not new.get('allowed_groups'):
            new['allowed_groups'] = ['webshare']

        await self._validate(new)

        # Handle dataset creation/updates
        await self._update_datasets(old, new)

        # Save configuration
        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            new['id'],
            new,
            {'prefix': self._config.datastore_prefix}
        )

        # Mount datasets if they were created
        await self._verify_datasets_mounted()

        # Generate configuration files
        await self._generate_config_files()

        # Set directory permissions
        await self._set_directory_permissions()

        # Reload service if running
        if await self.middleware.call('service.started', 'webshare'):
            await self.middleware.call('service.reload', 'webshare')

        return await self.config()

    @private
    async def _validate(self, data):
        """Validate WebShare configuration."""
        verrors = ValidationErrors()

        # Validate pool selections
        boot_pool = await self.middleware.call('boot.pool_name')
        pools = await self.middleware.call(
            'pool.query', [['status', '!=', 'OFFLINE']]
        )
        pool_names = [p['name'] for p in pools if p['name'] != boot_pool]

        for field in ['bulk_download_pool', 'search_index_pool']:
            if data.get(field):
                if data[field] not in pool_names:
                    verrors.add(
                        f'webshare_update.{field}',
                        f'Pool "{data[field]}" is not a valid imported pool'
                    )

        # Validate altroots
        if data.get('altroots'):
            # Check unique keys (handled by dict structure)
            # Check unique values
            values = list(data['altroots'].values())
            if len(values) != len(set(values)):
                verrors.add(
                    'webshare_update.altroots',
                    'Duplicate values are not allowed in altroots'
                )

            # Validate paths
            for name, path in data['altroots'].items():
                await self._validate_pool_path(
                    verrors, 'webshare_update.altroots', name, path, pool_names
                )

        # Validate search directories
        if data.get('search_directories'):
            for idx, path in enumerate(data['search_directories']):
                await self._validate_pool_path(
                    verrors, 'webshare_update.search_directories',
                    f'[{idx}]', path, pool_names
                )

        # Validate time format
        if data.get('search_pruning_start_time'):
            time_str = data['search_pruning_start_time']
            valid = False

            try:
                # Check format is exactly HH:MM
                if len(time_str) == 5 and time_str[2] == ':':
                    hour_str, minute_str = time_str.split(':')
                    # Check both parts are exactly 2 digits
                    if (len(hour_str) == 2 and len(minute_str) == 2 and
                            hour_str.isdigit() and minute_str.isdigit()):
                        hour = int(hour_str)
                        minute = int(minute_str)
                        if 0 <= hour <= 23 and 0 <= minute <= 59:
                            valid = True
            except (ValueError, AttributeError):
                pass

            if not valid:
                verrors.add(
                    'webshare_update.search_pruning_start_time',
                    'Invalid time format. Use HH:MM (24-hour format)'
                )

        # Validate numeric ranges
        if data.get('search_index_cleanup_threshold') is not None:
            if not 0 <= data['search_index_cleanup_threshold'] <= 100:
                verrors.add(
                    'webshare_update.search_index_cleanup_threshold',
                    'Threshold must be between 0 and 100 (percentage)'
                )

        # Validate allowed_groups
        if data.get('allowed_groups') is not None:
            if not isinstance(data['allowed_groups'], list):
                verrors.add(
                    'webshare_update.allowed_groups',
                    'Must be a list of group names'
                )
            elif not data['allowed_groups']:
                verrors.add(
                    'webshare_update.allowed_groups',
                    'At least one group must be specified'
                )
            else:
                # Validate that groups exist on the system
                groups = await self.middleware.call('group.query')
                valid_groups = [g['group'] for g in groups]

                for group in data['allowed_groups']:
                    if not isinstance(group, str):
                        verrors.add(
                            'webshare_update.allowed_groups',
                            'Group names must be strings'
                        )
                    elif group not in valid_groups:
                        verrors.add(
                            'webshare_update.allowed_groups',
                            f'Group "{group}" does not exist on the system'
                        )

        verrors.check()

    @private
    async def _validate_pool_path(self, verrors, field_base, field_name,
                                  path, pool_names):
        """Validate that a path is under /mnt/<poolname>/ and exists."""
        if not path.startswith('/mnt/'):
            verrors.add(
                f'{field_base}.{field_name}',
                f'Path must be under /mnt/<poolname>/, got: {path}'
            )
            return

        # Extract pool name from path
        path_parts = path[5:].split('/', 1)  # Remove '/mnt/' prefix
        if not path_parts or path_parts[0] not in pool_names:
            verrors.add(
                f'{field_base}.{field_name}',
                f'Path must be under a valid pool in /mnt/, got: {path}'
            )
            return

        # Check if path exists
        try:
            await self.middleware.call('filesystem.stat', path)
        except Exception:
            verrors.add(
                f'{field_base}.{field_name}',
                f'Path does not exist or is not accessible: {path}'
            )

    @private
    async def _update_datasets(self, old_config, new_config):
        """Create or update WebShare private datasets."""
        dataset_configs = [
            ('bulk_download_pool', 'bulk_download',
             {'compression': 'lz4', 'atime': 'off'}),
            ('search_index_pool', 'search-index', {
                'compression': 'lz4', 'atime': 'off', 'recordsize': '16K'
            })
        ]

        for pool_field, dataset_suffix, properties in dataset_configs:
            old_pool = old_config.get(pool_field)
            new_pool = new_config.get(pool_field)

            if old_pool != new_pool:
                # Remove old dataset if pool changed
                if old_pool:
                    old_dataset = (
                        f'{old_pool}/.webshare-private/{dataset_suffix}'
                    )
                    old_dataset_exists = await self.middleware.call(
                        'zfs.dataset.query', [['name', '=', old_dataset]]
                    )
                    if old_dataset_exists:
                        await self.middleware.call(
                            'zfs.dataset.delete', old_dataset,
                            {'recursive': True}
                        )

            # Create or update dataset if pool is set
            if new_pool:
                parent_dataset = f'{new_pool}/.webshare-private'
                dataset = f'{parent_dataset}/{dataset_suffix}'

                # Create parent if needed
                parent_exists = await self.middleware.call(
                    'zfs.dataset.query', [['name', '=', parent_dataset]]
                )
                if not parent_exists:
                    await self.middleware.call(
                        'zfs.dataset.create', {
                            'name': parent_dataset,
                            'properties': {}
                        }
                    )

                # Create dataset
                dataset_exists = await self.middleware.call(
                    'zfs.dataset.query',
                    [['name', '=', dataset]]
                )
                if not dataset_exists:
                    # Create dataset with default ZFS mount behavior
                    await self.middleware.call(
                        'zfs.dataset.create', {
                            'name': dataset,
                            'properties': properties
                        }
                    )
                    # Mount the dataset after creation
                    await self.middleware.call(
                        'zfs.dataset.mount', dataset
                    )
                    # Set permissions immediately after creation
                    if dataset_suffix == 'search-index':
                        await self._set_search_index_permissions(dataset)
                else:
                    # Dataset exists, ensure it's mounted
                    ds = dataset_exists[0]
                    mountpoint = ds['properties']['mountpoint']['value']
                    if mountpoint == 'none' or not ds.get('mounted', False):
                        await self.middleware.call(
                            'zfs.dataset.mount', dataset
                        )

    @private
    async def _get_dataset_paths(self):
        """Get the actual mount paths for WebShare datasets."""
        config = await self.config()
        paths = {}

        dataset_configs = [
            ('bulk_download_pool', 'bulk_download', 'bulk_download_path'),
            ('search_index_pool', 'search-index', 'search_index_path')
        ]

        for pool_field, dataset_suffix, path_key in dataset_configs:
            pool = config.get(pool_field)
            if pool:
                dataset = f'{pool}/.webshare-private/{dataset_suffix}'

                # Query dataset to get its actual mount point
                datasets = await self.middleware.call(
                    'zfs.dataset.query',
                    [['name', '=', dataset]]
                )

                if datasets:
                    props = datasets[0]['properties']
                    mountpoint = props['mountpoint']['value']
                    if mountpoint and mountpoint != 'none':
                        paths[path_key] = mountpoint
                    else:
                        # Dataset exists but not mounted
                        paths[path_key] = None
                else:
                    # Dataset doesn't exist
                    paths[path_key] = None
            else:
                paths[path_key] = None

        return paths

    @private
    async def _verify_datasets_mounted(self):
        """Verify WebShare datasets are properly mounted."""
        paths = await self._get_dataset_paths()
        errors = []

        for path_key, path in paths.items():
            if path_key == 'bulk_download_path' and path is None:
                config = await self.config()
                if config.get('bulk_download_pool'):
                    errors.append('Bulk download dataset is not mounted')
            elif path_key == 'search_index_path' and path is None:
                config = await self.config()
                if config.get('search_index_pool') and \
                        config.get('search_enabled'):
                    errors.append('Search index dataset is not mounted')

        if errors:
            raise CallError('. '.join(errors))

    @private
    async def _set_search_index_permissions(self, dataset_name):
        """Set ownership for search index dataset after creation."""
        # Get the actual mount point of the dataset
        datasets = await self.middleware.call(
            'zfs.dataset.query',
            [['name', '=', dataset_name]]
        )

        if not datasets:
            self.logger.warning(f'Dataset {dataset_name} not found')
            return

        mountpoint = datasets[0]['properties']['mountpoint']['value']
        if not mountpoint or mountpoint == 'none':
            self.logger.warning(f'Dataset {dataset_name} has no mountpoint')
            return

        try:
            # Use middleware's filesystem.chown for ownership
            chown_job = await self.middleware.call('filesystem.chown', {
                'path': mountpoint,
                'uid': None,  # Will be resolved by username
                'gid': None,  # Will be resolved by group name
                'user': 'truesearch',
                'group': 'truesearch',
                'options': {
                    'recursive': False,
                    'traverse': False
                }
            })
            await chown_job.wait(raise_error=True)
            self.logger.info(
                f'Set ownership of {mountpoint} to truesearch:truesearch')
        except Exception as e:
            self.logger.warning(
                f'Failed to set ownership for {mountpoint}: {e}'
            )

    @private
    async def _set_directory_permissions(self):
        """Set proper ownership and permissions for WebShare directories."""
        paths = await self._get_dataset_paths()

        # Set ownership for search index directory to truesearch user/group
        index_dir = paths.get('search_index_path')
        if index_dir:
            try:
                # Use middleware's filesystem.chown for recursive ownership
                chown_job = await self.middleware.call('filesystem.chown', {
                    'path': index_dir,
                    'uid': None,  # Will be resolved by username
                    'gid': None,  # Will be resolved by group name
                    'user': 'truesearch',
                    'group': 'truesearch',
                    'options': {
                        'recursive': False,
                        'traverse': False
                    }
                })
                await chown_job.wait(raise_error=True)
            except Exception as e:
                self.logger.warning(
                    f'Failed to set ownership for {index_dir}: {e}'
                )

        # Set permissions for bulk download directory to 777
        bulk_download_dir = paths.get('bulk_download_path')
        if bulk_download_dir:
            try:
                # Use middleware's filesystem.setperm for permissions
                setperm_job = await self.middleware.call(
                    'filesystem.setperm', {
                        'path': bulk_download_dir,
                        'mode': '777',
                        'uid': None,
                        'gid': None,
                        'options': {
                            'recursive': False,
                            'traverse': False
                        }
                    })
                await setperm_job.wait(raise_error=True)
            except Exception as e:
                self.logger.warning(
                    f'Failed to set permissions for {bulk_download_dir}: {e}'
                )

    @private
    async def _generate_config_files(self):
        """Generate configuration files for WebShare services."""
        config = await self.config()

        # Get actual mount paths from datasets
        paths = await self._get_dataset_paths()
        bulk_download_tmp = paths.get('bulk_download_path')
        search_index_path = paths.get('search_index_path')

        # Create config directories
        config_dirs = [
            '/etc/webshare-auth',
            '/etc/truenas-file-manager',
            '/etc/truesearch'
        ]
        for config_dir in config_dirs:
            pathlib.Path(config_dir).mkdir(parents=True, exist_ok=True)

        # Generate truenas-webshare-auth config
        auth_config = {
            'truenashost': config['truenas_host'],
            'webshare_config_path': '/etc/truenas-file-manager/config.json',
            'log_level': config['log_level'],
            'pam_service_name': config['pam_service_name'],
            'allowed_groups': config['allowed_groups'] or ['webshare'],
            'bulk_download_tmp': (
                bulk_download_tmp or
                '/var/tmp/truenas-file-manager/bulk-downloads'
            ),
            'session_log_retention': config['session_log_retention'],
            'enable_web_terminal': config['enable_web_terminal'],
            'truesearch': {
                'enabled': config['search_enabled'],
                'config': '/etc/truesearch/config.json',
                'debug': config['log_level'] == 'debug'
            }
        }

        with open('/etc/webshare-auth/config.json', 'w') as f:
            json.dump(auth_config, f, indent=2)

        # Generate truenas-file-manager config
        fm_config = {
            'altroots': config['altroots'],
            'bulk_download_tmp': (
                bulk_download_tmp or
                '/var/tmp/truenas-file-manager/bulk-downloads'
            )
        }

        with open('/etc/truenas-file-manager/config.json', 'w') as f:
            json.dump(fm_config, f, indent=2)

        # Generate truesearch config if search is enabled
        if config['search_enabled']:
            # Convert schedule to interval hours
            schedule_hours = {
                'hourly': 1,
                'daily': 24,
                'weekly': 168
            }

            # Include WebShare paths that have search_indexed enabled
            search_dirs = list(config['search_directories'])
            altroots_metadata = config.get('altroots_metadata', {})
            for name, path in config['altroots'].items():
                if altroots_metadata.get(name, {}).get('search_indexed', True):
                    if path not in search_dirs:
                        search_dirs.append(path)

            search_config = {
                'directories': search_dirs,
                'index_path': search_index_path or './index',
                'log_level': config['log_level'],
                'max_file_size': config['search_max_file_size'],
                'supported_types': config['search_supported_types'],
                'batch_size': 100,
                'worker_count': config['search_worker_count'],
                'archive': {
                    'max_depth': config['search_archive_max_depth'],
                    'max_entries': 1000,
                    'max_archive_size': config['search_archive_max_size'],
                    'index_contents': config['search_archive_enabled'],
                    'extract_text': False,
                    'supported_formats': [
                        'zip', 'tar', 'gz', 'bz2', 'xz', 'rar', '7z'
                    ]
                },
                'index_settings': {
                    'max_index_size': config['search_index_max_size'],
                    'max_document_count': 1000000,
                    'cleanup_policy': 'lru',
                    'cleanup_threshold': (
                        config['search_index_cleanup_threshold'] / 100.0
                    ),
                    'enable_auto_cleanup': (
                        config['search_index_cleanup_enabled']
                    ),
                    'cleanup_cooldown_minutes': 5,
                    'cleanup_target': 0.8
                },
                'pruning': {
                    'enabled': config['search_pruning_enabled'],
                    'schedule': config['search_pruning_schedule'],
                    'interval_hours': schedule_hours.get(
                        config['search_pruning_schedule'], 24
                    ),
                    'start_time': config['search_pruning_start_time'],
                    'verify_on_startup': False,
                    'remove_orphaned': True,
                    'batch_size': 1000,
                    'max_duration_minutes': 120
                },
                'security': {
                    'processing_timeout_seconds': 300,
                    'max_compression_ratio': 100.0,
                    'max_decompressed_size': 10737418240,
                    'max_memory_per_file': 104857600,
                    'enable_panic_recovery': True,
                    'validate_archive_paths': True,
                    'max_text_file_size': 10485760,
                    'restart_workers_on_panic': True
                },
                'reindex': {
                    'enabled': False,
                    'schedule': 'weekly',
                    'interval_hours': 168,
                    'start_time': '02:00',
                    'max_duration_minutes': 240,
                    'clean_index': False
                }
            }

            with open('/etc/truesearch/config.json', 'w') as f:
                json.dump(search_config, f, indent=2)

    @private
    async def check_configuration(self):
        """Check if WebShare service can start with current configuration."""
        # Auto-configure pools if not set
        await self._auto_configure_pools_if_needed()

        config = await self.config()
        errors = []

        # Check if required pools are configured (after auto-configuration)
        if not config['bulk_download_pool']:
            errors.append(
                'No bulk download pool configured. '
                'Please configure a pool in WebShare settings.'
            )
        if not config['search_index_pool'] and config['search_enabled']:
            errors.append(
                'No search index pool configured. '
                'Please configure a pool or disable search.'
            )

        # Check if datasets exist and are properly mounted
        paths = await self._get_dataset_paths()

        # Check bulk download dataset
        if config.get('bulk_download_pool'):
            if paths.get('bulk_download_path') is None:
                dataset = (f"{config['bulk_download_pool']}/"
                           ".webshare-private/bulk_download")
                errors.append(
                    f'Dataset {dataset} does not exist or is not mounted')

        # Check search index dataset
        if config.get('search_index_pool') and config['search_enabled']:
            if paths.get('search_index_path') is None:
                dataset = (f"{config['search_index_pool']}/"
                           ".webshare-private/search-index")
                errors.append(
                    f'Dataset {dataset} does not exist or is not mounted')

        if errors:
            raise CallError('\n'.join(errors))

    @private
    async def _auto_configure_pools_if_needed(self):
        """Auto-configure pools if not set when service is manually started."""
        config = await self.config()

        # Only auto-configure if pools are not already set
        if config['bulk_download_pool'] and config['search_index_pool']:
            return

        # Get available pools for automatic selection
        boot_pool = await self.middleware.call('boot.pool_name')
        pools = await self.middleware.call(
            'pool.query', [['status', '!=', 'OFFLINE']]
        )
        available_pools = [p['name'] for p in pools if p['name'] != boot_pool]

        if not available_pools:
            # No pools available, let check_configuration handle the error
            return

        # Auto-select first available pool
        update_data = {}

        if not config['bulk_download_pool']:
            update_data['bulk_download_pool'] = available_pools[0]
            self.logger.info(
                f'Auto-selecting pool "{available_pools[0]}" for bulk download'
            )

        if not config['search_index_pool']:
            update_data['search_index_pool'] = available_pools[0]
            self.logger.info(
                f'Auto-selecting pool "{available_pools[0]}" for search index'
            )

        if update_data:
            # Update configuration
            await self.middleware.call('webshare.update', update_data)

    @private
    async def before_start(self):
        """Called before starting the service."""
        # check_configuration will auto-configure pools if needed
        await self.check_configuration()
        await self._verify_datasets_mounted()
        await self._generate_config_files()
        await self._set_directory_permissions()
