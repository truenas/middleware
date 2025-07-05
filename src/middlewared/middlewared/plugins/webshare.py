import json
import os
import pathlib

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.schema import ValidationErrors
from middlewared.service import CallError, SystemServiceService, private, job

from middlewared.api.current import (
    WebShareEntry, WebShareUpdateArgs,
    WebShareUpdateResult,
    WebShareValidateArgs,
    WebShareValidateResult,
    WebShareRemovePasskeyArgs,
    WebShareRemovePasskeyData,
    WebShareRemovePasskeyResult
)


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
    srv_shares = sa.Column(sa.JSON(list), default=[])
    srv_home_directory_template = sa.Column(
        sa.String(255), default='{{.Username}}'
    )
    srv_home_directory_perms = sa.Column(sa.String(4), default='0700')
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
    srv_proxy_port = sa.Column(sa.Integer(), default=755)
    srv_proxy_bind_addrs = sa.Column(sa.JSON(list), default=['0.0.0.0'])
    srv_storage_admins = sa.Column(sa.Boolean(), default=False)
    srv_passkey_mode = sa.Column(sa.String(20), default='disabled')
    srv_passkey_rp_origins = sa.Column(sa.JSON(list), default=[])


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

        `shares` defines the file shares configuration. Each share has:
        - `name`: Unique name for the share
        - `path`: Filesystem path under /mnt/<poolname>/
        - `is_home_base`: Whether this share is the base for user home
          directories

        Only one share can have `is_home_base` set to true. Home base
        shares are
        not displayed as regular shares but are used as the base path for
        dynamic
        home directory creation.

        `home_directory_template` defines the template for home directory
        names,
        supporting {{.Username}}, {{.UID}}, and {{.GID}} placeholders.

        `home_directory_perms` sets the permissions for newly created home
        directories.

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
            await self.middleware.call(
                'service.reload', 'webshare', {'timeout': 30}
            )

        # Start/restart truesearch service if needed, passing old config
        # to detect changes
        await self._manage_truesearch_service(old_config=old)

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

        # Validate shares
        if data.get('shares') is not None:
            # Check for duplicate names
            share_names = [
                share['name'] for share in data['shares']
                if 'name' in share
            ]
            if len(share_names) != len(set(share_names)):
                verrors.add(
                    'webshare_update.shares',
                    'Duplicate share names are not allowed'
                )

            # Check for duplicate paths
            share_paths = [
                share['path'] for share in data['shares']
                if 'path' in share
            ]
            if len(share_paths) != len(set(share_paths)):
                verrors.add(
                    'webshare_update.shares',
                    'Duplicate share paths are not allowed'
                )

            # Check only one home base
            home_base_count = sum(1 for share in data['shares']
                                  if share.get('is_home_base', False))
            if home_base_count > 1:
                verrors.add(
                    'webshare_update.shares',
                    'Only one share can be marked as home base'
                )

            # Validate each share
            for idx, share in enumerate(data['shares']):
                if 'name' not in share:
                    verrors.add(
                        f'webshare_update.shares[{idx}]',
                        'Share name is required'
                    )
                elif not share['name']:
                    verrors.add(
                        f'webshare_update.shares[{idx}].name',
                        'Share name cannot be empty'
                    )

                if 'path' not in share:
                    verrors.add(
                        f'webshare_update.shares[{idx}]',
                        'Share path is required'
                    )
                else:
                    await self._validate_pool_path(
                        verrors, f'webshare_update.shares[{idx}]',
                        'path', share['path'], pool_names
                    )

        # Validate search directories
        if data.get('search_directories'):
            for idx, path in enumerate(data['search_directories']):
                await self._validate_pool_path(
                    verrors, 'webshare_update.search_directories',
                    f'[{idx}]', path, pool_names
                )

        # Validate home directory template (only if explicitly provided)
        if ('home_directory_template' in data and
                data['home_directory_template']):
            template = data['home_directory_template']
            # Basic validation for Go template syntax
            valid_placeholders = ['{{.Username}}', '{{.UID}}', '{{.GID}}']
            # Check if template contains any valid placeholders
            has_placeholder = any(
                placeholder in template
                for placeholder in valid_placeholders
            )
            if not has_placeholder:
                verrors.add(
                    'webshare_update.home_directory_template',
                    'Template must contain at least one placeholder: '
                    '{{.Username}}, {{.UID}}, or {{.GID}}'
                )

        # Validate home directory permissions (only if explicitly provided)
        if 'home_directory_perms' in data and data['home_directory_perms']:
            perms = data['home_directory_perms']
            # Validate octal permissions format
            try:
                if len(perms) == 4 and perms[0] == '0':
                    # Convert from string octal (e.g., '0755') to int
                    perms_int = int(perms, 8)
                else:
                    # Assume it's already in format like '755'
                    perms_int = int(perms, 8)

                # Check valid range (000 to 777)
                if not (0 <= perms_int <= 0o777):
                    raise ValueError()
            except (ValueError, TypeError):
                verrors.add(
                    'webshare_update.home_directory_perms',
                    'Invalid permissions format. Use octal notation '
                    '(e.g., "0755" or "755")'
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

        # Validate proxy port
        if data.get('proxy_port') is not None:
            port = data['proxy_port']
            if not isinstance(port, int):
                verrors.add(
                    'webshare_update.proxy_port',
                    'Proxy port must be an integer'
                )
            elif not 1 <= port <= 65535:
                verrors.add(
                    'webshare_update.proxy_port',
                    'Proxy port must be between 1 and 65535'
                )

        # Validate proxy bind addresses
        if data.get('proxy_bind_addrs') is not None:
            bind_addrs = data['proxy_bind_addrs']
            if not isinstance(bind_addrs, list):
                verrors.add(
                    'webshare_update.proxy_bind_addrs',
                    'Proxy bind addresses must be a list'
                )
            elif not bind_addrs:
                verrors.add(
                    'webshare_update.proxy_bind_addrs',
                    'At least one bind address must be specified'
                )
            else:
                for idx, addr in enumerate(bind_addrs):
                    if not isinstance(addr, str):
                        verrors.add(
                            f'webshare_update.proxy_bind_addrs[{idx}]',
                            'Bind address must be a string'
                        )
                    # Basic validation - could be IP or "0.0.0.0" or hostname
                    elif not addr:
                        verrors.add(
                            f'webshare_update.proxy_bind_addrs[{idx}]',
                            'Bind address cannot be empty'
                        )

        # Validate passkey mode
        if data.get('passkey_mode') is not None:
            mode = data['passkey_mode']
            valid_modes = ['disabled', 'enabled', 'required']
            if mode not in valid_modes:
                verrors.add(
                    'webshare_update.passkey_mode',
                    f'Invalid passkey mode. Must be one of: '
                    f'{", ".join(valid_modes)}'
                )

        # Validate passkey rp_origins
        if data.get('passkey_rp_origins') is not None:
            if not isinstance(data['passkey_rp_origins'], list):
                verrors.add(
                    'webshare_update.passkey_rp_origins',
                    'RP origins must be a list of URLs'
                )
            else:
                for idx, origin in enumerate(data['passkey_rp_origins']):
                    if not isinstance(origin, str):
                        verrors.add(
                            f'webshare_update.passkey_rp_origins[{idx}]',
                            'Origin must be a string URL'
                        )
                    elif not origin:
                        verrors.add(
                            f'webshare_update.passkey_rp_origins[{idx}]',
                            'Origin cannot be empty'
                        )
                    elif not origin.startswith('https://'):
                        verrors.add(
                            f'webshare_update.passkey_rp_origins[{idx}]',
                            'Origin must be a valid HTTPS URL starting with '
                            'https://'
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
        self.logger.debug('Generating WebShare configuration files')

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
            },
            'proxy': {
                'enabled': True,
                'port': config['proxy_port'],
                'bind_addrs': config['proxy_bind_addrs'],
                'cert_path': '/etc/certificates',
                'cert_prefix': 'truenas_connect',
                'dhparam_path': '/data/dhparam.pem',
                'timeouts': {
                    'read_timeout_seconds': 86400,
                    'write_timeout_seconds': 86400,
                    'idle_timeout_seconds': 86400,
                    'stream_timeout_seconds': 86400,
                    'header_timeout_seconds': 60,
                    'shutdown_timeout_seconds': 30
                }
            },
            'passkey': {
                'mode': config['passkey_mode'],
                'rp_name': 'TrueNAS WebShare',
                'rp_display_name': 'TrueNAS WebShare',
                'rp_id': 'truenas.direct',
                'rp_origins': config['passkey_rp_origins'] or [],
                'timeout': 60000
            },
            'webshare_link': {
                'enabled': True,
                'binary_path': '/usr/bin/truenas-webshare-link',
                'config_path': '/etc/webshare-link/config.json',
                'port': 756,
                'database_path': '/var/lib/truenas-webshare-auth/webshare.db',
                'health_check_url': 'https://127.0.0.1:756/health',
                'startup_timeout_seconds': 30,
                'restart_on_failure': True,
                'max_restarts': 5,
                'restart_delay_seconds': 10,
                'log_level': 'info',
                'auto_start': True
            }
        }

        with open('/etc/webshare-auth/config.json', 'w') as f:
            json.dump(auth_config, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Ensure file is written to disk

        # Generate truenas-file-manager config
        fm_config = {
            'shares': config['shares'],
            'home_directory_template': config['home_directory_template'],
            'home_directory_perms': config['home_directory_perms'],
            'bulk_download_tmp': (
                bulk_download_tmp or
                '/var/tmp/truenas-file-manager/bulk-downloads'
            ),
            'storage_admins': config['storage_admins']
        }

        with open('/etc/truenas-file-manager/config.json', 'w') as f:
            json.dump(fm_config, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Ensure file is written to disk

        # Update truesearch config if any shares have search indexing enabled
        has_search_indexed_shares = any(
            share.get('search_indexed', True)
            for share in config.get('shares', [])
        )

        if config['search_enabled'] or has_search_indexed_shares:
            self.logger.debug(
                f'Updating truesearch config - '
                f'global_search_enabled={config["search_enabled"]}, '
                f'has_search_indexed_shares={has_search_indexed_shares}'
            )
            await self._update_truesearch_config(config, search_index_path)
        else:
            self.logger.debug(
                'Skipping truesearch config update - no search-indexed shares'
            )

    @private
    async def _update_truesearch_config(self, config, search_index_path):
        """Update truesearch config file, preserving existing settings."""
        truesearch_config_path = '/etc/truesearch/config.json'

        # Read existing config or create default structure
        try:
            with open(truesearch_config_path, 'r') as f:
                search_config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Create default config if file doesn't exist or is invalid
            search_config = {
                'directories': [],
                'index_path': '/var/lib/truesearch/index',
                'log_level': 'info',
                'exclude_patterns': [
                    '*.tmp',
                    '*.cache',
                    '*.log',
                    '.git/*',
                    'node_modules/*'
                ],
                'file_types': ['*']
            }

        # Collect WebShare paths from regular shares (not home base)
        webshare_dirs = list(config['search_directories'])
        self.logger.debug(
            f'WebShare config has {len(config.get("shares", []))} shares'
        )

        for share in config['shares']:
            self.logger.debug(
                f'Processing share: {share.get("name")} - '
                f'is_home_base={share.get("is_home_base", False)}, '
                f'search_indexed={share.get("search_indexed", True)}, '
                f'path={share.get("path")}'
            )
            # Include all shares (regular AND home base) that have
            # search_indexed enabled
            if share.get('search_indexed', True):
                path = share.get('path')
                if path and path not in webshare_dirs:
                    webshare_dirs.append(path)
                    self.logger.debug(
                        f'Added share path to webshare directories: {path}'
                    )

        # Update only the directories managed by WebShare
        # Preserve any existing directories that aren't from WebShare
        existing_dirs = search_config.get('directories', [])

        # Filter out old webshare directories (assume they start with /mnt/)
        # This is a simple heuristic - could be improved with better tracking
        non_webshare_dirs = [
            d for d in existing_dirs if not d.startswith('/mnt/')
        ]

        # Combine non-webshare directories with current webshare directories
        search_config['directories'] = non_webshare_dirs + webshare_dirs

        # Update index path if we have one configured
        if search_index_path:
            search_config['index_path'] = search_index_path

        self.logger.debug(
            f'Updated truesearch directories: {search_config["directories"]}'
        )

        # Write the updated config
        with open(truesearch_config_path, 'w') as f:
            json.dump(search_config, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Ensure file is written to disk

        # After updating config, start/restart the truesearch service if needed
        await self._manage_truesearch_after_config_update(config)

    @private
    async def _manage_truesearch_after_config_update(self, config):
        """Start or restart truesearch service after config update."""
        # Check if we have any search-indexed shares
        has_search_indexed_shares = any(
            share.get('search_indexed', True)
            for share in config.get('shares', [])
        )

        # Only manage service if global search is enabled OR we have
        # search-indexed shares
        should_run_truesearch = (
            config.get('search_enabled', False) or has_search_indexed_shares
        )

        if not should_run_truesearch:
            self.logger.debug(
                'No search-indexed shares, skipping truesearch '
                'service management'
            )
            return

        # Check if truesearch service exists and is running
        try:
            truesearch_running = await self.middleware.call(
                'service.started', 'truesearch'
            )
        except Exception as e:
            # Service might not be registered/installed
            self.logger.debug(
                f'Could not check truesearch service status: {e}'
            )
            truesearch_running = False

        # Ensure truesearch config file exists before starting service
        if not os.path.exists('/etc/truesearch/config.json'):
            self.logger.warning(
                'TrueSearch config file not found, skipping service start'
            )
            return

        if truesearch_running:
            # Service is running - restart it to pick up config changes
            try:
                self.logger.info(
                    'Restarting truesearch service to apply '
                    'configuration changes'
                )
                await self.middleware.call('service.restart', 'truesearch', {})
            except Exception as e:
                self.logger.warning(
                    f'Failed to restart truesearch service: {e}'
                )
        else:
            # Service is not running - start it
            try:
                self.logger.info(
                    'Starting truesearch service for search-indexed shares'
                )
                await self.middleware.call('service.start', 'truesearch', {})
            except Exception as e:
                self.logger.warning(
                    f'Failed to start truesearch service: {e}'
                )

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
    async def _auto_configure_pools_if_needed(self, skip_reload=False):
        """Auto-configure pools if not set when service is manually started.

        Args:
            skip_reload: If True, update database directly without triggering
                service reload
        """
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
            if skip_reload:
                # Update database directly without triggering service
                # reload. This is used during service startup to avoid
                # circular dependency
                config.update(update_data)
                await self.middleware.call(
                    'datastore.update',
                    self._config.datastore,
                    config['id'],
                    config,
                    {'prefix': self._config.datastore_prefix}
                )
                # Still need to create datasets
                await self._update_datasets(config, config)
            else:
                # Normal update path
                await self.middleware.call('webshare.update', update_data)

    @private
    async def _manage_truesearch_service(self, old_config=None):
        """Start or stop truesearch service based on webshare configuration.

        Args:
            old_config: Previous configuration to detect changes. If None,
                skip change detection.
        """
        config = await self.config()

        # Check if search is enabled in the configuration
        search_enabled = config.get('search_enabled', False)

        # Check if any shares have search indexing enabled
        has_search_indexed_shares = any(
            share.get('search_indexed', True)
            for share in config.get('shares', [])
        )

        # TrueSearch should run if search is enabled and there are
        # search-indexed shares
        should_run_truesearch = search_enabled and has_search_indexed_shares

        # Check if truesearch service exists and is running
        try:
            truesearch_running = await self.middleware.call(
                'service.started', 'truesearch'
            )
        except Exception as e:
            # Service might not be registered/installed
            self.logger.debug(
                f'Could not check truesearch service status: {e}'
            )
            truesearch_running = False

        if should_run_truesearch and not truesearch_running:
            # Ensure config file exists before starting
            if not os.path.exists('/etc/truesearch/config.json'):
                self.logger.warning(
                    'TrueSearch config file not found, cannot start service'
                )
                return

            try:
                self.logger.info(
                    'Starting truesearch service as webshare has '
                    'search-enabled shares'
                )
                await self.middleware.call('service.start', 'truesearch', {})
            except Exception as e:
                self.logger.warning(
                    f'Failed to start truesearch service: {e}'
                )
        elif not should_run_truesearch and truesearch_running:
            # Only stop if webshare is the only reason it's running
            # For now, we'll just log a warning rather than stopping it
            self.logger.info(
                'WebShare no longer requires truesearch service'
            )
        elif (should_run_truesearch and truesearch_running and
              old_config is not None):
            # Check if we need to restart due to directory changes
            old_dirs = self._get_search_directories(old_config)
            new_dirs = self._get_search_directories(config)

            if set(old_dirs) != set(new_dirs):
                try:
                    self.logger.info(
                        'Restarting truesearch service due to '
                        'directory changes'
                    )
                    await self.middleware.call(
                        'service.restart', 'truesearch', {}
                    )
                except Exception as e:
                    self.logger.warning(
                        f'Failed to restart truesearch service: {e}'
                    )

    @private
    def _get_search_directories(self, config):
        """Extract all search directories from configuration."""
        directories = list(config.get('search_directories', []))

        # Add all share paths (regular AND home base) that have
        # search_indexed enabled
        for share in config.get('shares', []):
            if share.get('search_indexed', True):
                path = share.get('path')
                if path and path not in directories:
                    directories.append(path)

        return directories

    @private
    async def before_start(self):
        """Called before starting the service."""
        # check_configuration will auto-configure pools if needed
        await self.check_configuration()
        await self._verify_datasets_mounted()
        await self._generate_config_files()
        await self._set_directory_permissions()

        # Add a small delay to ensure config files are fully synced to disk
        # This prevents race conditions where systemd starts services before
        # config files are available
        await self.middleware.run_in_thread(self._ensure_config_files_exist)

        # Start truesearch if needed when webshare starts
        await self._manage_truesearch_service()

    @private
    def _ensure_config_files_exist(self):
        """Verify that all required config files exist and are readable."""
        import time
        config_files = [
            '/etc/webshare-auth/config.json',
            '/etc/truenas-file-manager/config.json'
        ]

        # Check up to 5 times with 0.1 second delay
        for _ in range(5):
            all_exist = True
            for config_file in config_files:
                if (not os.path.exists(config_file) or
                        not os.path.isfile(config_file)):
                    all_exist = False
                    break
                try:
                    # Try to read the file to ensure it's accessible
                    with open(config_file, 'r') as f:
                        json.load(f)
                except Exception:
                    all_exist = False
                    break

            if all_exist:
                return

            time.sleep(0.1)

        # If we get here, files still don't exist
        missing_files = [f for f in config_files if not os.path.exists(f)]
        if missing_files:
            raise CallError(
                f"Config files not found after generation: "
                f"{', '.join(missing_files)}"
            )

    @api_method(WebShareRemovePasskeyArgs, WebShareRemovePasskeyResult,
                roles=['SHARING_WRITE'])
    @job(lock='webshare_remove_passkey')
    async def remove_passkey(self, job, username):
        """
        Remove passkey for a specific user using truenas-webshare-auth command.

        Args:
            username: The username to remove passkey for

        Returns:
            dict: Result of the operation
        """
        import subprocess

        if not username:
            raise CallError('Username is required')

        if not isinstance(username, str):
            raise CallError('Username must be a string')

        # Validate that config file exists
        config_file = '/etc/webshare-auth/config.json'
        if not os.path.exists(config_file):
            raise CallError(
                'WebShare auth config file not found. '
                'Please ensure WebShare service is configured.'
            )

        try:
            # Run truenas-webshare-auth -config /etc/webshare-auth/config.json
            # -remove-passkey <username>
            cmd = [
                'truenas-webshare-auth',
                '-config', config_file,
                '-remove-passkey', username
            ]

            self.logger.info(
                f'Removing passkey for user: {username}'
            )

            result = await self.middleware.run_in_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else (
                    'Unknown error occurred'
                )
                raise CallError(
                    f'Failed to remove passkey for user {username}: '
                    f'{error_msg}'
                )

            output = result.stdout.strip() if result.stdout else ''
            self.logger.info(
                f'Successfully removed passkey for user {username}. '
                f'Output: {output}'
            )

            return WebShareRemovePasskeyData(
                username=username,
                success=True,
                message=f'Passkey removed for user: {username}',
                output=output
            )

        except subprocess.TimeoutExpired:
            raise CallError(
                f'Command timed out while removing passkey for '
                f'user: {username}'
            )
        except Exception as e:
            self.logger.error(
                f'Error removing passkey for user {username}: {e}'
            )
            raise CallError(
                f'Failed to remove passkey for user {username}: {str(e)}'
            )
