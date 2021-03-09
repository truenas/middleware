import asyncio
import contextlib
import errno
import os
import subprocess as su
import itertools
import pathlib
import json
import sqlite3
import re

import iocage_lib.iocage as ioc
import iocage_lib.ioc_exceptions as ioc_exceptions
import iocage_lib.ioc_common as ioc_common
from iocage_lib.ioc_check import IOCCheck
from iocage_lib.ioc_clean import IOCClean
from iocage_lib.ioc_image import IOCImage
from iocage_lib.ioc_json import IOCJson
# iocage's imports are per command, these are just general facilities
from iocage_lib.ioc_list import IOCList
from iocage_lib.ioc_plugin import IOCPlugin
from iocage_lib.release import ListableReleases

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.schema import Bool, Dict, Int, List, Str, accepts, Patch
from middlewared.service import CRUDService, job, private, filterable, periodic, item_method
from middlewared.service_exception import CallError, ValidationErrors
from middlewared.utils import filter_list, run
from middlewared.validators import IpInUse, MACAddr

from pkg_resources import parse_version

from collections import deque, Iterable

BRANCH_REGEX = re.compile(r'\d+\.\d-RELEASE')

SHUTDOWN_LOCK = asyncio.Lock()


def validate_ips(middleware, verrors, options, schema='options.props', exclude=None):
    for item in options['props']:
        for f in ('ip4_addr', 'ip6_addr'):
            # valid ip values can be
            # 1) none
            # 2) interface|accept_rtadv
            # 3) interface|ip/netmask
            # 4) interface|ip
            # 5) ip/netmask
            # 6) ip
            # 7) All the while making sure that the above can be mixed with each other using ","
            # we explicitly check these
            if f in item:
                for ip in map(
                        lambda ip: ip.split('|', 1)[-1].split('/')[0],
                        filter(
                            lambda v: v != 'none' and v.split('|')[-1] != 'accept_rtadv',
                            item.split('=')[1].split(',')
                        )
                ):
                    try:
                        IpInUse(middleware, exclude)(ip)
                    except ValueError as e:
                        verrors.add(f'{schema}.{f}', str(e))


def common_validation(middleware, options, update=False, jail=None, schema='options'):
    verrors = ValidationErrors()

    if not update:
        # Ensure that api call conforms to format set by iocage for props
        # Example 'key=value'

        for value in options['props']:
            if '=' not in value:
                verrors.add(
                    f'{schema}.props',
                    'Please follow the format specified by iocage for api calls'
                    'e.g "key=value"'
                )
                break

        if verrors:
            raise verrors

        # normalise vnet mac address
        # expected format here is 'vnet0_mac=00-D0-56-F2-B5-12,00-D0-56-F2-B5-13'
        vnet_macs = {
            f.split('=')[0]: f.split('=')[1] for f in options['props']
            if any(f'vnet{i}_mac' in f.split('=')[0] for i in range(0, 4))
        }

        validate_ips(middleware, verrors, options, schema=f'{schema}.props')
    else:
        vnet_macs = {
            key: value for key, value in options.items()
            if any(f'vnet{i}_mac' in key for i in range(0, 4))
        }

        exclude_ips = [
            ip.split('|')[1].split('/')[0] if '|' in ip else ip.split('/')[0]
            for f in ('ip4_addr', 'ip6_addr') for ip in jail[f].split(',')
            if ip not in ('none', 'DHCP (not running)')
        ]

        validate_ips(
            middleware, verrors, {'props': [f'{k}={v}' for k, v in options.items()]},
            schema, exclude_ips
        )

    # validate vnetX_mac addresses
    for key, value in vnet_macs.items():
        if value and value != 'none':
            value = value.replace(',', ' ')
            try:
                for mac in value.split():
                    MACAddr()(mac)

                if len(value.split()) != 2 or any(value.split().count(v) > 1 for v in value.split()):
                    raise ValueError('Exception')
            except ValueError:
                verrors.add(
                    f'{schema}.{key}',
                    'Please enter two valid and different '
                    f'space/comma-delimited MAC addresses for {key}.'
                )

    if options.get('uuid'):
        valid = True if re.match(
            r"^[a-zA-Z0-9\._-]+$", options['uuid']
        ) else False

        if not valid:
            verrors.add(
                f'{schema}.uuid',
                f'Invalid character in {options["uuid"]}. '
                'Alphanumeric, period (.), underscore (_), '
                'and dash (-) characters are allowed.'
            )

    return verrors


class PluginService(CRUDService):

    class Config:
        cli_private = True

    @accepts()
    async def official_repositories(self):
        """
        List officially supported plugin repositories.
        """
        is_ent = await self.middleware.call('system.is_enterprise')
        repos = {
            'IXSYSTEMS': {
                'name': 'iXsystems',
                'git_repository': f'https://github.com/{"freenas" if not is_ent else "truenas"}/iocage-ix-plugins.git'
            }
        }
        if not is_ent:
            repos.update({
                'COMMUNITY': {
                    'name': 'Community',
                    'git_repository': 'https://github.com/ix-plugin-hub/iocage-plugin-index.git'
                }
            })
        return repos

    @private
    def default_repo(self):
        return self.middleware.call_sync('plugin.official_repositories')['IXSYSTEMS']['git_repository']

    @filterable
    def query(self, filters, options):
        """
        Query installed plugins with `query-filters` and `query-options`.
        """
        if not self.middleware.call_sync('jail.iocage_set_up'):
            return []

        options = options or {}
        self.middleware.call_sync('jail.check_dataset_existence')  # Make sure our datasets exist.
        iocage = ioc.IOCage(skip_jails=True)
        resource_list = iocage.list('all', plugin=True, plugin_data=True)
        iocroot = self.middleware.call_sync('jail.get_iocroot')

        for index, plugin in enumerate(resource_list):
            # "plugin" is a list which we will convert to a dictionary for readability
            plugin_dict = {
                k: v if v != '-' else None
                for k, v in zip((
                    'jid', 'name', 'boot', 'state', 'type', 'release', 'ip4',
                    'ip6', 'template', 'admin_portal', 'doc_url', 'plugin',
                    'plugin_repository', 'primary_pkg', 'category', 'maintainer',
                ), plugin)
            }
            plugin_output = pathlib.Path(f'{iocroot}/jails/{plugin_dict["name"]}/root/root/PLUGIN_INFO')
            plugin_info = plugin_output.read_text().strip() if plugin_output.is_file() else None
            admin_portal = plugin_dict.pop('admin_portal')

            plugin_dict.update({
                'id': plugin_dict['name'],
                'plugin_info': plugin_info,
                'admin_portals': admin_portal.split(',') if admin_portal else [],
                **self.get_local_plugin_version(
                    plugin_dict['plugin'],
                    plugin_dict.pop('primary_pkg'), iocroot, plugin_dict['name']
                )
            })

            resource_list[index] = plugin_dict

        return filter_list(resource_list, filters, options)

    @accepts(
        Dict(
            'plugin_create',
            Str('plugin_name', required=True),
            Str('jail_name', required=True),
            List('props'),
            Str('branch', default=None, null=True),
            Str('plugin_repository', empty=False),
        )
    )
    @job(lock=lambda args: f'plugin_create_{args[0]["jail_name"]}')
    def do_create(self, job, data):
        """
        Create a Plugin.

        `plugin_name` is the name of the plugin specified by the INDEX file in "plugin_repository" and it's JSON
        file.

        `jail_name` is the name of the jail that will manage the plugin. Required.

        `props` is a list of jail properties that the user manually sets. Plugins should always set the jail
        networking capability with DHCP, IP Address, or NAT properties. i.e dhcp=1 / ip4_addr="192.168.0.2" / nat=1

        `plugin_repository` is a git URI that fetches data for `plugin_name`.

        `branch` is the FreeNAS repository branch to use as the base for the `plugin_repository`. The default is to
        use the current system version. Example: 11.3-RELEASE.
        """
        self.middleware.call_sync('network.general.will_perform_activity', 'jail')
        data['plugin_repository'] = data.get('plugin_repository') or self.default_repo()
        self.middleware.call_sync('jail.check_dataset_existence')
        verrors = ValidationErrors()
        branch = data.pop('branch') or self.get_version()
        install_notes = ''
        plugin_name = data.pop('plugin_name')
        jail_name = data.pop('jail_name')
        plugin_repository = data.pop('plugin_repository')
        post_install = False

        job.set_progress(0, f'Creating plugin: {plugin_name}')
        if jail_name in [j['id'] for j in self.middleware.call_sync('jail.query')]:
            verrors.add(
                'plugin_create.jail_name',
                f'A jail with name {jail_name} already exists'
            )
        else:
            verrors = common_validation(self.middleware, data, schema='plugin_create')

        self.middleware.call_sync(
            'jail.failover_checks', {
                'id': jail_name, 'host_hostuuid': jail_name,
                **self.middleware.call_sync('jail.complete_default_configuration'),
                **self.defaults({
                    'plugin': plugin_name, 'plugin_repository': plugin_repository, 'branch': branch, 'refresh': True
                })['properties'],
                **{
                    v.split('=')[0]: v.split('=')[-1] for v in data['props']
                }
            }, verrors, 'plugin_create'
        )
        verrors.check()

        job.set_progress(20, 'Initial validation complete')

        def progress_callback(content, exception):
            msg = content['message'].strip('\r\n')
            nonlocal install_notes, post_install

            if post_install and msg:
                install_notes += f'\n{msg}'

            if '  These pkgs will be installed:' in msg:
                job.set_progress(50, msg)
            elif 'Installing plugin packages:' in msg:
                job.set_progress(75, msg)
            elif 'Running post_install.sh' in msg:
                job.set_progress(90, msg)
                # Sets each message going forward as important to the user
                post_install = True
            else:
                job.set_progress(None, msg)

        ioc.IOCage(callback=progress_callback, silent=False).fetch(**{
            'accept': True,
            'name': jail_name,
            'plugin_name': plugin_name,
            'git_repository': plugin_repository,
            'props': data['props'],
            'branch': branch,
        })

        new_plugin = self.middleware.call_sync('plugin.get_instance', jail_name)
        new_plugin['install_notes'] = install_notes.strip()

        return new_plugin

    @accepts(
        Str('id'),
        Patch('jail_update', 'plugin_update')
    )
    async def do_update(self, id, data):
        """
        Update plugin `id`.
        """
        await self._get_instance(id)
        return await self.middleware.call('jail.update', id, data)

    @accepts(Str('id'))
    async def do_delete(self, id):
        """
        Delete plugin `id`.
        """
        await self._get_instance(id)
        return await self.middleware.call('jail.delete', id)

    @private
    def retrieve_index_plugins_data(self, branch, plugin_repository, refresh=True):
        data = {'plugins': None, 'index': None}
        iocage_tmp_dir = '/tmp/iocage/.plugins'
        os.makedirs(iocage_tmp_dir, exist_ok=True)
        plugin_dir = os.path.join(iocage_tmp_dir, self.convert_repository_to_path(plugin_repository))
        try:
            if refresh or not os.path.exists(plugin_dir):
                IOCPlugin._clone_repo(branch, plugin_repository, plugin_dir)
        except Exception:
            self.middleware.logger.error(f'Failed to clone {plugin_repository}.', exc_info=True)
        else:
            data['plugins'] = IOCPlugin.retrieve_plugin_index_data(plugin_dir)
            if os.path.exists(os.path.join(plugin_dir, 'INDEX')):
                with open(os.path.join(plugin_dir, 'INDEX'), 'r') as f:
                    data['index'] = json.loads(f.read())

        return data

    @periodic(interval=86400)
    async def retrieve_versions_for_repos(self):
        for repo in (await self.official_repositories()).values():
            await self.middleware.call('plugin.available', {'plugin_repository': repo['git_repository']})

    @accepts(
        Dict(
            'available_plugin_options',
            Bool('cache', default=True),
            Str('plugin_repository', empty=False),
            Str('branch'),
        )
    )
    @job()
    def available(self, job, options):
        """
        List available plugins which can be fetched for `plugin_repository`.
        """
        self.middleware.call_sync('network.general.will_perform_activity', 'jail')
        default_branch = self.get_version()
        default_repo = self.default_repo()
        options['branch'] = options.get('branch') or default_branch
        options['plugin_repository'] = options.get('plugin_repository') or default_repo
        return self.middleware.call_sync('plugin.available_impl', options).wait_sync(raise_error=True)

    @job(lock=lambda args: f'available_plugins_{args[0]["plugin_repository"]}_{args[0]["branch"]}')
    @private
    def available_impl(self, job, options):
        branch = options['branch']
        plugin_repository = options['plugin_repository']

        if options['cache']:
            with contextlib.suppress(KeyError):
                return self.middleware.call_sync(
                    'cache.get', f'iocage_remote_plugins_{branch}_{options["plugin_repository"]}'
                )

        if not self.middleware.call_sync('jail.iocage_set_up'):
            cloned_repo = self.retrieve_index_plugins_data(branch, plugin_repository)
            if any(not cloned_repo[k] for k in ('plugins', 'index')):
                return []

            plugins_versions_data = IOCPlugin.fetch_plugin_versions_from_plugin_index(cloned_repo['plugins'])
            resource_list = [
                {
                    'plugin': plugin,
                    **{k: d.get(k, '') for k in ('description', 'icon', 'name', 'license', 'official', 'category')}
                }
                for plugin, d in cloned_repo['index'].items()
            ]
        else:
            self.middleware.call_sync('jail.check_dataset_existence')
            plugins_versions_data = IOCPlugin(branch=branch, git_repository=plugin_repository).fetch_plugin_versions()
            try:
                resource_list = ioc.IOCage(skip_jails=True).fetch(
                    list=True, plugins=True, header=False, branch=branch, git_repository=options['plugin_repository']
                )
            except Exception as e:
                resource_list = []
                self.middleware.logger.debug(
                    'Failed to retrieve plugins for %s: %s', options['plugin_repository'], str(e)
                )

        for plugin in resource_list:
            plugin.update({
                k: plugins_versions_data.get(plugin['plugin'], {}).get(k, 'N/A')
                for k in ('version', 'revision', 'epoch')
            })

        self.middleware.call_sync(
            'cache.put', f'iocage_remote_plugins_{branch}_{options["plugin_repository"]}', resource_list,
            86400
        )

        return resource_list

    @accepts(
        Dict(
            'options',
            Bool('refresh', default=False),
            Str('plugin', required=True),
            Str('branch', default=None, null=True),
            Str('plugin_repository', emtpy=False)
        )
    )
    def defaults(self, options):
        """
        Retrieve default properties specified for `plugin` in the plugin's manifest.

        When `refresh` is specified, `plugin_repository` is updated before retrieving plugin's default properties.
        """
        plugin_repository = options.get('plugin_repository') or self.default_repo()
        branch = options['branch'] or self.get_version()

        if not self.middleware.call_sync('jail.iocage_set_up'):
            index = self.retrieve_index_plugins_data(branch, plugin_repository, options['refresh'])
            index = index['plugins'] or {}
        else:
            self.middleware.call_sync('jail.check_dataset_existence')
            plugins_obj = IOCPlugin(branch=branch, git_repository=plugin_repository)
            if not os.path.exists(plugins_obj.git_destination) or options['refresh']:
                plugins_obj.pull_clone_git_repo()
            index = plugins_obj.retrieve_plugin_index_data(plugins_obj.git_destination)

        if options['plugin'] not in index:
            raise CallError(
                f'{options["plugin"]} not found, likely because local plugin repository is corrupted.'
            )
        return {
            'plugin': options['plugin'],
            'properties': {**IOCPlugin.DEFAULT_PROPS, **index[options['plugin']].get('properties', {})}
        }

    @accepts(
        Str('repository', default=None, null=True, empty=False)
    )
    async def branches_choices(self, repository):
        repository = repository or self.default_repo()

        cp = await run(['git', 'ls-remote', repository], check=False, encoding='utf8')
        if cp.returncode:
            raise CallError(f'Failed to retrieve branches for {repository}: {cp.stderr}')

        return {
            branch: {'official': bool(BRANCH_REGEX.match(branch))}
            for branch in re.findall(r'refs/heads/(.*)', cp.stdout)
        }

    @accepts(
        Str('jail'),
        Bool('update_jail', default=True)
    )
    @job(lock=lambda args: f'jail_update:{args[0]}')
    async def update_plugin(self, job, jail, update_jail=True):
        """
        Updates specified plugin to latest available plugin version and optionally update plugin to latest patch level.
        """
        return await self.middleware.call('jail.update_to_latest_patch_internal', job, jail, False, update_jail)

    @periodic(interval=86400)
    @private
    def periodic_plugin_update(self):
        plugin_available = self.middleware.call_sync('plugin.available')
        plugin_available.wait_sync()
        self.middleware.call_sync('plugin.plugin_updates')

    @private
    @job(lock='plugin_versions')
    def retrieve_plugin_versions(self, job, plugins):
        self.middleware.call_sync('network.general.will_perform_activity', 'jail')
        return IOCPlugin.fetch_plugin_versions_from_plugin_index(plugins)

    @private
    @job(lock='plugin_updates')
    def plugin_updates(self, job):
        plugins = self.query()
        if not plugins:
            return

        index_data = {}
        for repo in map(lambda p: p['plugin_repository'], plugins):
            if repo not in index_data:
                index_obj = IOCPlugin(git_repository=repo, branch=self.get_version())
                index = index_obj.retrieve_plugin_index_data(index_obj.git_destination, expand_abi=False)
                if index:
                    index_data[repo] = index

        installed_plugins = []
        for plugin in filter(
            lambda p: index_data.get(p['plugin_repository'], {}).get(p['plugin']),
            plugins
        ):
            ioc_plugin = IOCPlugin(
                plugin=plugin['plugin'], git_repository=plugin['plugin_repository'],
                branch=self.get_version(), jail=plugin['name'],
            )

            try:
                plugin_manifest = ioc_plugin._plugin_json_file()
            except Exception:
                plugin_manifest = {}
            installed_plugins.append({
                **plugin,
                'plugin_manifest': plugin_manifest,
                'plugin_git_manifest': index_data[plugin['plugin_repository']][plugin['plugin']],
            })

        if not installed_plugins:
            return

        # There are 2 cases, one is where we check the version of the installed plugin with available, next is
        # we check the plugin manifest version with the installed plugin's manifest. If any of the case is true,
        # we raise an alert for the plugin update

        # There are 2 cases which we have to handle wrt packagesite
        # 1) Plugin is using a packagesite which does not have ${ABI}
        # 2) Plugin is using a packagesite which has ${ABI}
        # Case (1) is not special and just retrieving available plugin version from it's git repository
        # is sufficient. However with Case (2), If a user has 11.3 jail and host is 12, available version
        # will default to using the release specified in the manifest which is usually the same as host version.
        # So assume Host is at 12, available version release is at 12, but the jail is at 11 release. So ABI
        # will infact expand to "FreeBSD:11:amd64" instead of "FreeBSD:12:amd64". We need to account for this
        # in how we determine if a plugin update is available for a specified plugin
        def major_version(version):
            return version.split('-')[0].split('.')[0]

        git_repos = {}
        custom_plugin_versions = {}
        custom_plugin_versions_job = None
        for plugin in installed_plugins:
            if (
                major_version(plugin['plugin_git_manifest']['release']) != major_version(plugin['release']) and
                '${ABI}' in plugin['plugin_git_manifest']['packagesite']
            ):
                # If the version in new git manifest is same as major version of plugin release,
                # we don't need to do this as plugin.available will give us similar results
                custom_plugin_versions[plugin['name']] = {
                    **plugin['plugin_git_manifest'],
                    'packagesite': IOCPlugin.expand_abi_with_specified_release(
                        plugin['plugin_git_manifest']['packagesite'], plugin['release']
                    ),
                }
            else:
                repo = plugin['plugin_repository']
                if repo not in git_repos:
                    git_repos[repo] = self.middleware.call_sync('plugin.available', {'plugin_repository': repo})

        if custom_plugin_versions:
            custom_plugin_versions_job = self.middleware.call_sync(
                'plugin.retrieve_plugin_versions', custom_plugin_versions
            )

        for repo, job_obj in git_repos.items():
            job_obj.wait_sync()
            if job_obj.error:
                self.middleware.logger.error(f'Failed to retrieve plugin versions for {repo}: {job_obj.error}')
                git_repos[repo] = []
            else:
                git_repos[repo] = job_obj.result

        if custom_plugin_versions_job:
            custom_plugin_versions_job.wait_sync()
            if custom_plugin_versions_job.error:
                self.middleware.logger.error(
                    'Failed to retrieve available versions for "%s" plugins: %s',
                    ', '.join(custom_plugin_versions), custom_plugin_versions_job.error
                )
                custom_plugin_versions = {k: {} for k in custom_plugin_versions}
            else:
                custom_plugin_versions = custom_plugin_versions_job.result

        for plugin in installed_plugins:
            if plugin['name'] in custom_plugin_versions:
                plugin_dict = custom_plugin_versions[plugin['name']]
                if not plugin_dict:
                    # We were unable to retrieve available plugin versions for this plugin
                    continue
            else:
                repo = plugin['plugin_repository']
                plugin_dict = (list(filter(lambda d: d['plugin'] == plugin['plugin'], git_repos[repo])) or [{}])[0]

            if not plugin_dict or any(
                plugin_dict[k] == 'N/A' or plugin[k] == 'N/A' for k in ('version', 'revision', 'epoch')
            ):
                # We don't support update alerts for plugins without a valid port
                continue

            plugin_git_manifest = plugin['plugin_git_manifest']
            plugin_manifest = plugin['plugin_manifest']

            # We construct our version in the following manner
            # epoch!manifest_version.version.revision
            available_version = f'{plugin_dict["epoch"]}!{plugin_git_manifest.get("revision", "0")}.' \
                                f'{plugin_dict["version"]}.{plugin_dict["revision"]}'
            plugin_version = f'{plugin["epoch"]}!{plugin_manifest.get("revision", "0")}.' \
                             f'{plugin["version"]}.{plugin["revision"]}'

            if parse_version(plugin_version) < parse_version(available_version):
                # Raise an alert please, this plugin needs an update
                self.middleware.call_sync('alert.oneshot_create', 'PluginUpdate', plugin)

    @private
    def get_version(self):
        """
        Uses system.version and parses it out for the RELEASE branch we need
        """
        r = os.uname().release
        version = f'{round(float(r.split("-")[0]), 1)}-RELEASE'

        return version

    @private
    def get_local_plugin_version(self, plugin, primary_pkg, iocroot, jail_name):
        """
        Checks the primary_pkg key in the INDEX with the pkg version
        inside the jail.
        """
        version = {k: 'N/A' for k in ('version', 'revision', 'epoch')}

        primary_pkg = primary_pkg or plugin
        if not primary_pkg:
            return version

        try:
            # Since these are plugins, we don't want to spin them up just to
            # check a pkg, directly accessing the db is best in this case.
            db_rows = self.read_plugin_pkg_db(
                f'{iocroot}/jails/{jail_name}/root/var/db/pkg/local.sqlite', primary_pkg
            )

            for row in db_rows:
                row = list(row)
                if '/' not in primary_pkg:
                    row[1] = row[1].split('/', 1)[-1]
                    row[2] = row[2].split('/', 1)[-1]

                if primary_pkg == row[1] or primary_pkg == row[2]:
                    version = ioc_common.parse_package_name(f'{plugin}-{row[3]}')
                    break
        except (KeyError, sqlite3.OperationalError):
            pass

        return version

    @private
    def read_plugin_pkg_db(self, db, pkg):
        try:
            conn = sqlite3.connect(db)
        except sqlite3.Error as e:
            self.middleware.logger.error('Failed to connect to %r database : %s', db, str(e))
            return []

        with conn:
            cur = conn.cursor()
            cur.execute(
                f'SELECT * FROM packages WHERE origin="{pkg}" OR name="{pkg}"'
            )

            rows = cur.fetchall()

            return rows

    @private
    def convert_repository_to_path(self, git_repository_uri):
        # Following is the logic which iocage uses to ensure unique directory names for each uri
        return git_repository_uri.split('://', 1)[-1].replace('/', '_').replace('.', '_')


class JailService(CRUDService):

    class Config:
        cli_private = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # We want debug for jails starting/stopping
        os.environ['IOCAGE_DEBUG'] = 'TRUE'

    @filterable
    def query(self, filters, options):
        """
        Query all jails with `query-filters` and `query-options`.
        """
        options = options or {}
        jail_identifier = None
        jails = []

        if not self.iocage_set_up():
            return []

        self.check_dataset_existence()

        if filters and len(filters) == 1 and list(
                filters[0][:2]) == ['host_hostuuid', '=']:
            jail_identifier = filters[0][2]

        recursive = False if jail_identifier == 'default' else True

        try:
            jail_dicts = ioc.IOCage(
                jail=jail_identifier).get('all', recursive=recursive)

            if jail_identifier == 'default':
                jail_dicts['host_hostuuid'] = 'default'
                jails.append(jail_dicts)
            else:
                for jail in jail_dicts:
                    jail = list(jail.values())[0]
                    jail['id'] = jail['host_hostuuid']
                    if jail['dhcp']:
                        uuid = jail['host_hostuuid'].replace('.', '_')

                        if jail['state'] == 'up':
                            interface = jail['interfaces'].split(',')[0].split(
                                ':')[0]
                            if interface == 'vnet0':
                                # Inside jails they are epair0b
                                interface = 'epair0b'
                            ip4_cmd = ['jexec', f'ioc-{uuid}', 'ifconfig',
                                       interface, 'inet']
                            try:
                                out = su.check_output(ip4_cmd)
                                out = out.splitlines()[2].split()[1].decode()
                                jail['ip4_addr'] = f'{interface}|{out}'
                            except (su.CalledProcessError, IndexError):
                                jail['ip4_addr'] = f'{interface}|ERROR'
                        else:
                            jail['ip4_addr'] = 'DHCP (not running)'
                    jails.append(jail)
        except ioc_exceptions.JailMisconfigured as e:
            self.logger.error(e, exc_info=True)
        except Exception:
            # Brandon is working on fixing this generic except, till then I
            # am not going to make the perfect the enemy of the good enough!
            self.logger.debug('Failed to get list of jails', exc_info=True)

        return filter_list(jails, filters, options)

    @private
    def iocage_set_up(self):
        datasets = self.middleware.call_sync(
            'zfs.dataset.query',
            [['properties.org\\.freebsd\\.ioc:active.value', '=', 'yes']],
            {'extra': {'properties': ['encryption', 'keystatus', 'mountpoint'], 'flat': False}}
        )
        return not (not datasets or not any(
            d['name'].endswith('/iocage') and (not d['encrypted'] or (d['encrypted'] and d['key_loaded']))
            for root_dataset in datasets for d in root_dataset['children']
        ))

    @accepts()
    def default_configuration(self):
        """
        Retrieve default configuration for iocage jails.
        """
        return {
            k: v for k, v in self.complete_default_configuration().items()
            if k not in IOCJson.default_only_props
        }

    @private
    def complete_default_configuration(self):
        if not self.iocage_set_up():
            return IOCJson.retrieve_default_props()
        else:
            return self.query(filters=[['host_hostuuid', '=', 'default']], options={'get': True})

    @accepts(
        Bool('remote', default=False),
    )
    def releases_choices(self, remote):
        """
        List installed or available releases which can be downloaded.
        """
        if remote:
            with contextlib.suppress(KeyError):
                return self.middleware.call_sync('cache.get', 'iocage_remote_releases')

        choices = {str(k): str(k) for k in ListableReleases(remote=remote)}

        if remote:
            self.middleware.call_sync('cache.put', 'iocage_remote_releases', choices, 86400)

        return choices

    @accepts(
        Dict(
            "options",
            Str("release", required=True),
            Str("template"),
            List("pkglist", items=[Str("pkg", empty=False)]),
            Str("uuid", required=True),
            Bool("basejail", default=False),
            Bool("empty", default=False),
            Bool("short", default=False),
            List("props"),
            Bool('https', default=True)
        )
    )
    @job(lock=lambda args: f'jail_create:{args[0]["uuid"]}')
    def do_create(self, job, options):
        """Creates a jail."""
        # Typically one would return the created jail's id in this
        # create call BUT since jail creation may or may not involve
        # fetching a release, which in turn could be time consuming
        # and could then block for a long time. This dictates that we
        # make it a job, but that violates the principle that CRUD methods
        # are not jobs as yet, so I settle on making this a wrapper around
        # the main job that calls this and return said job's id instead of
        # the created jail's id
        verrors = ValidationErrors()
        uuid = options["uuid"]

        job.set_progress(0, f'Creating: {uuid}')

        try:
            self.check_jail_existence(uuid, skip=False)

            verrors.add(
                'uuid',
                f'A jail with name {uuid} already exists'
            )
            raise verrors
        except CallError:
            # A jail does not exist with the provided name, we can create one
            # now

            verrors = common_validation(self.middleware, options)

            self.failover_checks({
                'id': uuid,
                'host_hostuuid': uuid,
                **self.middleware.call_sync('jail.complete_default_configuration'), **{
                    v.split('=')[0]: v.split('=')[-1] for v in options['props']
                }
            }, verrors, 'options')
            verrors.check()
            job.set_progress(20, 'Initial validation complete')

        iocage = ioc.IOCage(skip_jails=True)

        release = options["release"]
        template = options.get("template", False)
        pkglist = options.get("pkglist", None)
        basejail = options["basejail"]
        empty = options["empty"]
        short = options["short"]
        props = options["props"]
        pool = IOCJson().json_get_value("pool")
        iocroot = IOCJson(pool).json_get_value("iocroot")
        https = options.get('https', True)

        if template:
            release = template

        if (
            not os.path.isdir(f'{iocroot}/releases/{release}') and not template and not empty
        ):
            job.set_progress(50, f'{release} missing, calling fetch')
            fetch_job = self.middleware.call_sync(
                'jail.fetch', {"release": release, "https": https}
            )
            fetch_job.wait_sync()
            if fetch_job.error:
                raise CallError(fetch_job.error)

        err, msg = iocage.create(
            release,
            props,
            0,
            pkglist,
            template=template,
            short=short,
            _uuid=uuid,
            basejail=basejail,
            empty=empty
        )

        if err:
            raise CallError(msg)

        job.set_progress(100, f'Created: {uuid}')

        return self.middleware.call_sync('jail.get_instance', uuid)

    @item_method
    @accepts(
        Str('source_jail', empty=False),
        Dict(
            'clone_jail',
            Str('uuid', required=True, empty=False),
            List('pkglist', items=[Str('pkg', empty=False)]),
            Bool('thickjail', default=False),
            List('props'),
        )
    )
    @job(lock=lambda args: f'clone_jail:{args[0]}')
    def clone(self, job, source_jail, options):
        verrors = ValidationErrors()
        try:
            self.check_jail_existence(source_jail, skip=False)
        except CallError:
            verrors.add(
                'source_jail',
                f'{source_jail} does not exist.', errno.ENOENT
            )
        else:
            try:
                self.check_jail_existence(options['uuid'], skip=False)
            except CallError:
                pass
            else:
                verrors.add(
                    'clone_jail.uuid',
                    f'Jail with "{options["uuid"]}" uuid already exists.', errno.EEXIST
                )

        verrors.check()
        verrors = common_validation(self.middleware, options, schema='clone_jail')
        verrors.check()

        job.set_progress(25, 'Initial validation complete.')

        ioc.IOCage(jail=source_jail, skip_jails=True).create(
            source_jail, options['props'], _uuid=options['uuid'], thickjail=options['thickjail'], clone=True
        )

        job.set_progress(100, 'Jail has been successfully cloned.')

        return self.middleware.call_sync('jail.get_instance', options['uuid'])

    @accepts(
        Str('jail'),
        Dict(
            'jail_update',
            Bool('plugin', default=False),
            additional_attrs=True,
            register=True
        )
    )
    def do_update(self, jail, options):
        """Sets a jail property."""
        plugin = options.pop("plugin")
        _, _, iocage = self.check_jail_existence(jail)

        name = options.pop("name", None)

        jail = self.query([['id', '=', jail]], {'get': True})

        verrors = common_validation(self.middleware, options, True, jail)

        if name is not None and plugin:
            verrors.add('options.plugin', 'Cannot be true while trying to rename')

        self.failover_checks({**jail, **options}, verrors, 'options')
        verrors.check()

        opts = {}
        if 'bpf' in options and 'nat' in options:
            # We do this as props are applied sequentially, this will allow end user to apply
            # the props bpf/nat without making separate calls for them as they are mutually exclusive
            if options['bpf']:
                opts.update({'nat': options.pop('nat'), 'bpf': options.pop('bpf')})
            else:
                opts.update({'bpf': options.pop('bpf'), 'nat': options.pop('nat')})
        opts.update(options)

        for prop, val in opts.items():
            p = f"{prop}={val}"

            try:
                iocage.set(p, plugin)
            except RuntimeError as err:
                raise CallError(err)

        if name:
            iocage.rename(name)

        return True

    @accepts(
        Str('jail'),
        Dict(
            'options',
            Bool('force', default=False),
        )
    )
    def do_delete(self, jail, options):
        """Takes a jail and destroys it."""
        _, _, iocage = self.check_jail_existence(jail)

        # TODO: Port children checking, release destroying.
        iocage.destroy_jail(force=options.get('force'))
        return True

    @private
    def check_dataset_existence(self):
        try:
            IOCCheck(migrate=True, reset_cache=True)
        except ioc_exceptions.PoolNotActivated as e:
            raise CallError(e, errno=errno.ENOENT)

    @private
    def check_jail_existence(self, jail, skip=True, callback=None):
        """Wrapper for iocage's API, as a few commands aren't ported to it"""
        try:
            iocage = ioc.IOCage(callback=callback, skip_jails=skip, jail=jail, reset_cache=True)
            # We use match_to_dir as __check_jail_existence__ searches greedily meaning if
            # we for example have a jail abcdef and wanted to check if abcd exists, it will say it does
            # and give us abcdef jail.
            if not ioc_common.match_to_dir(iocage.iocroot, jail):
                raise CallError(f'{jail!r} jail does not exist', errno=errno.ENOENT)

            jail, path = iocage.__check_jail_existence__()
        except RuntimeError:
            raise CallError(f'{jail!r} jail does not exist', errno=errno.ENOENT)

        return jail, path, iocage

    @accepts()
    def get_activated_pool(self):
        """Returns the activated pool if there is one, or None"""
        if not self.iocage_set_up():
            return None
        try:
            pool = ioc.IOCage(skip_jails=True, reset_cache=True).get('', pool=True)
        except (RuntimeError, SystemExit) as e:
            raise CallError(f'Error occurred getting activated pool: {e}')
        except (ioc_exceptions.PoolNotActivated, FileNotFoundError):
            self.check_dataset_existence()

            try:
                pool = ioc.IOCage(skip_jails=True).get('', pool=True)
            except ioc_exceptions.PoolNotActivated:
                pool = None

        return pool

    @accepts()
    async def interface_choices(self):
        """
        Returns a dictionary of interface choices which can be used with creating/updating jails.
        """
        return await self.middleware.call(
            'interface.choices', {
                'exclude': ['lo', 'pflog', 'pfsync', 'tun', 'tap', 'epair', 'vnet', 'bridge']
            }
        )

    @accepts()
    async def vnet_default_interface_choices(self):
        """
        Returns a dictionary of interface choices which can be used with `vnet_default_interface` property.
        """
        return {'none': 'none', 'auto': 'auto', **(await self.interface_choices())}

    @accepts(
        Dict(
            'options',
            Str('release'),
            Str('server', default='download.freebsd.org'),
            Str('user', default='anonymous'),
            Str('password', default='anonymous@'),
            Str('name', default=None, null=True),
            Str('jail_name'),
            Bool('accept', default=True),
            Bool('https', default=True),
            List('props'),
            List(
                'files',
                default=['MANIFEST', 'base.txz', 'lib32.txz']
            ),
            Str('branch', default=None, null=True)
        )
    )
    @job(lock=lambda args: f"jail_fetch")
    def fetch(self, job, options):
        """Fetches a release or plugin."""
        self.middleware.call_sync('network.general.will_perform_activity', 'jail')
        release = options.get('release', None)
        https = options.pop('https', False)
        name = options.pop('name')
        jail_name = options.pop('jail_name', None)

        def progress_callback(content, exception):
            msg = content['message'].strip('\r\n')
            rel_up = f'* Updating {release} to the latest patch level... '

            if 'Downloading : base.txz' in msg and '100%' in msg:
                job.set_progress(5, msg)
            elif 'Downloading : lib32.txz' in msg and '100%' in msg:
                job.set_progress(10, msg)
            elif 'Downloading : doc.txz' in msg and '100%' in msg:
                job.set_progress(15, msg)
            elif 'Downloading : src.txz' in msg and '100%' in msg:
                job.set_progress(20, msg)
            if 'Extracting: base.txz' in msg:
                job.set_progress(25, msg)
            elif 'Extracting: lib32.txz' in msg:
                job.set_progress(50, msg)
            elif 'Extracting: doc.txz' in msg:
                job.set_progress(75, msg)
            elif 'Extracting: src.txz' in msg:
                job.set_progress(90, msg)
            elif rel_up in msg:
                job.set_progress(95, msg)
            else:
                job.set_progress(None, msg)

        self.check_dataset_existence()  # Make sure our datasets exist.
        start_msg = f'{release} being fetched'
        final_msg = f'{release} fetched'

        if name is None and https:
            if 'https' not in options['server']:
                options['server'] = f'https://{options["server"]}'

        if name is not None:
            # we want to create a plugin in this case
            plugin_job = self.middleware.call_sync(
                'plugin.create', {
                    'jail_name': jail_name,
                    'plugin_name': name,
                    'props': options['props'],
                })
            plugin_job.wait_sync()
            if plugin_job.error:
                raise CallError(plugin_job.error)

            return plugin_job.result
        else:
            # We are fetching a release in this case
            iocage = ioc.IOCage(callback=progress_callback, silent=False)
            job.set_progress(0, start_msg)
            iocage.fetch(**options)
            job.set_progress(100, final_msg)
            return True

    @accepts(Str("action", enum=["START", "STOP", "RESTART"]))
    def rc_action(self, action):
        """Does specified action on rc enabled (boot=on) jails"""
        if not self.iocage_set_up():
            return
        iocage = ioc.IOCage(rc=True, reset_cache=True)

        try:
            if action == "START":
                iocage.start()
            elif action == "STOP":
                iocage.stop()
            else:
                iocage.restart()
        except Exception as e:
            raise CallError(str(e))

        return True

    @accepts(Dict('props', additional_attrs=True))
    def update_defaults(self, props):
        """
        Update default properties for iocage which will remain true for all jails moving on i.e nat_backend
        """
        iocage = ioc.IOCage(jail='default', reset_cache=True)
        for prop in props:
            iocage.set(f'{prop}={props[prop]}')

    @private
    def retrieve_default_iface(self):
        default_ifaces = ioc_common.get_host_gateways()
        if default_ifaces['ipv4']['interface']:
            return default_ifaces['ipv4']['interface']
        elif default_ifaces['ipv6']['interface']:
            return default_ifaces['ipv6']['interface']

    @private
    def retrieve_vnet_interface(self, iface):
        if iface == 'auto':
            return self.retrieve_default_iface()
        elif iface != 'none':
            return iface
        else:
            return None

    @private
    def retrieve_vnet_bridge(self, interfaces):
        bridges = []
        for interface in interfaces.split(','):
            if interface.split(':')[-1] not in bridges:
                bridges.append(interface.split(':')[-1])
        return bridges

    @private
    def retrieve_nat_interface(self, iface):
        return self.retrieve_default_iface() if iface == 'none' else iface

    @private
    async def nic_capability_checks(self, jails=None, check_system_iface=True):
        """
        For vnet/nat based jails, when jail is started, if NIC has certain capabilities set, we experience a
        hiccup in the network traffic which can cause a failover to occur. This method returns
        interfaces which will be affected by this based on the jails user has.
        """
        jail_nics = []
        system_ifaces = {i['name']: i for i in await self.middleware.call('interface.query')}
        for jail in (
            await self.middleware.call('jail.query', [['OR', [['vnet', '=', 1], ['nat', '=', 1]]]])
            if not jails else jails
        ):
            nic = await self.middleware.call(
                f'jail.retrieve_{"nat" if jail["nat"] else "vnet"}_interface',
                jail['nat_interface' if jail['nat'] else 'vnet_default_interface']
            )
            if nic in system_ifaces:
                if not jail['nat']:
                    bridges = await self.middleware.call('jail.retrieve_vnet_bridge', jail['interfaces'])
                    if not bridges or not bridges[0]:
                        continue
                if not check_system_iface or not system_ifaces[nic]['disable_offload_capabilities']:
                    jail_nics.append(nic)
        return jail_nics

    @private
    def failover_checks(self, jail_config, verrors, schema):
        if self.middleware.call_sync('system.is_enterprise') and self.middleware.call_sync('failover.licensed'):
            jail_config = {
                k: ioc_common.check_truthy(v) if k in IOCJson.truthy_props else v for k, v in jail_config.items()
            }
            if jail_config.get('dhcp'):
                jail_config['vnet'] = 1
            if not (jail_config['vnet'] or jail_config['nat']):
                return
            to_disable_nics = self.middleware.call_sync('jail.nic_capability_checks', [jail_config])
            if to_disable_nics:
                option = 'nat' if jail_config['nat'] else 'vnet'
                verrors.add(
                    f'{schema}.{option}',
                    f'Capabilities must be disabled for {",".join(to_disable_nics)} interface '
                    f'in Network->Interfaces section before enabling {option}'
                )

    @accepts(Str('jail'))
    @job(lock=lambda args: f'jail_start:{args[0]}')
    def start(self, job, jail):
        """Takes a jail and starts it."""
        uuid, _, iocage = self.check_jail_existence(jail)
        status, _ = IOCList.list_get_jid(uuid)

        if not status:
            try:
                iocage.start(used_ports=[6000] + list(range(1025)))
            except Exception as e:
                raise CallError(str(e))
        else:
            raise CallError(f'{jail} is already running')

        self.middleware.call_sync('service.restart', 'mdns')

        return True

    @accepts(Str("jail"), Bool('force', default=False))
    @job(lock=lambda args: f'jail_stop:{args[0]}')
    def stop(self, job, jail, force):
        """Takes a jail and stops it."""
        uuid, _, iocage = self.check_jail_existence(jail)
        status, _ = IOCList.list_get_jid(uuid)

        if status:
            try:
                iocage.stop(force=force)
            except Exception as e:
                raise CallError(str(e))
        else:
            raise CallError(f'{jail} is not running')

            return True

    @accepts(Str('jail'))
    @job(lock=lambda args: f"jail_restart:{args[0]}")
    def restart(self, job, jail):
        """Takes a jail and restarts it."""
        uuid, _, iocage = self.check_jail_existence(jail)
        status, _ = IOCList.list_get_jid(uuid)

        if status:
            try:
                iocage.stop()
            except Exception as e:
                raise CallError(str(e))

        try:
            iocage.start()
        except Exception as e:
            raise CallError(str(e))

        self.middleware.call_sync('service.restart', 'mdns')

        return True

    @private
    def get_iocroot(self):
        return IOCJson().json_get_value('iocroot')

    @accepts(
        Str("jail"),
        Dict(
            "options",
            Str(
                "action", enum=["ADD", "REMOVE", "REPLACE", "LIST"],
                required=True
            ),
            Str("source"),
            Str("destination"),
            Str("fstype", default='nullfs'),
            Str("fsoptions", default='ro'),
            Str("dump", default='0'),
            Str("pass", default='0'),
            Int("index", default=None),
        ))
    def fstab(self, jail, options):
        """Manipulate a jails fstab"""
        jail_data = self.middleware.call_sync('jail.get_instance', jail)
        if jail_data['template'] and options['action'] != 'LIST':
            raise CallError(f'Unable to perform {options["action"]} action as {jail} is a template.')

        uuid, _, iocage = self.check_jail_existence(jail, skip=False)
        status, jid = IOCList.list_get_jid(uuid)
        action = options['action'].lower()
        index = options.get('index')

        if status and action != 'list':
            raise CallError(
                f'{jail} should not be running when adding a mountpoint')

        verrors = ValidationErrors()

        if action in ('add', 'replace', 'remove'):
            if action != 'remove' or index is None:
                # For remove we allow removing by index or mount, so if index is not specified
                # we should validate that rest of the fields exist.
                for f in ('source', 'destination', 'fstype', 'fsoptions', 'dump', 'pass'):
                    if not options.get(f):
                        verrors.add(
                            f'options.{f}',
                            f'This field is required with "{action}" action.'
                        )

            if action == 'replace' and index is None:
                verrors.add(
                    'options.index',
                    'Index cannot be "None" when replacing an fstab entry.'
                )

        verrors.check()

        source = options.get('source')
        if action in ('add', 'replace') and not os.path.exists(source):
            verrors.add(
                'options.source',
                'The provided path for the source does not exist.'
            )

        destination = options.get('destination')
        if destination:
            destination = f'/{destination}' if destination[0] != '/' else \
                destination
            dst = f'{self.get_iocroot()}/jails/{jail}/root'
            if dst not in destination:
                destination = f'{dst}{destination}'

            if os.path.exists(destination):
                if not os.path.isdir(destination):
                    verrors.add(
                        'options.destination',
                        'Destination is not a directory. Please provide a '
                        'empty directory for the destination.'
                    )
                elif os.listdir(destination):
                    verrors.add(
                        'options.destination',
                        'Destination directory must be empty.'
                    )
            else:
                os.makedirs(destination)

        # Setup defaults for library
        source = source or ''
        destination = destination or ''
        fstype = options.get('fstype')
        fsoptions = options.get('fsoptions')
        dump = options.get('dump')
        _pass = options.get('pass')

        if verrors:
            raise verrors

        try:
            _list = iocage.fstab(
                action, source, destination, fstype, fsoptions,
                dump, _pass, index=index
            )
        except ioc_exceptions.ValidationFailed as e:
            # CallError uses strings, the exception message may not always be a
            # list.
            if not isinstance(e.message, str) and isinstance(
                e.message,
                Iterable
            ):
                e.message = '\n'.join(e.message)

            self.logger.error(f'{e!r}')
            raise CallError(e.message)

        if action == "list":
            split_list = {}
            system_mounts = (
                '/root/bin', '/root/boot', '/root/lib', '/root/libexec',
                '/root/rescue', '/root/sbin', '/root/usr/bin',
                '/root/usr/include', '/root/usr/lib', '/root/usr/libexec',
                '/root/usr/sbin', '/root/usr/share', '/root/usr/libdata',
                '/root/usr/lib32'
            )

            for i in _list:
                fstab_entry = i[1]
                _fstab_type = 'SYSTEM' if fstab_entry[0].endswith(
                    system_mounts) else 'USER'

                split_list[i[0]] = {'entry': fstab_entry, 'type': _fstab_type}

            return split_list

        return True

    @accepts(Str("pool"))
    def activate(self, pool):
        """Activates a pool for iocage usage, and deactivates the rest."""
        pool = self.middleware.call_sync('pool.query', [['name', '=', pool]], {'get': True})
        iocage = ioc.IOCage(reset_cache=True, activate=True)
        try:
            iocage.activate(pool['name'])
        except Exception as e:
            raise CallError(f'Failed to activate {pool["name"]}: {e}')
        else:
            self.check_dataset_existence()
            return True

    @accepts(Str("ds_type", enum=["ALL", "JAIL", "TEMPLATE", "RELEASE"]))
    def clean(self, ds_type):
        """Cleans all iocage datasets of ds_type"""
        if not self.iocage_set_up():
            return

        ioc.IOCage.reset_cache()
        if ds_type == "JAIL":
            IOCClean().clean_jails()
        elif ds_type == "ALL":
            IOCClean().clean_all()
        elif ds_type == "TEMPLATE":
            IOCClean().clean_templates()

        return True

    @accepts(
        Str("jail"),
        List("command", required=True),
        Dict("options", Str("host_user", default="root"), Str("jail_user")))
    @job(lock=lambda args: f"jail_exec:{args[0]}")
    def exec(self, job, jail, command, options):
        """Issues a command inside a jail."""
        _, _, iocage = self.check_jail_existence(jail, skip=False)

        host_user = options["host_user"]
        jail_user = options.get("jail_user", None)

        if isinstance(command[0], list):
            # iocage wants a flat list, not a list inside a list
            command = list(itertools.chain.from_iterable(command))

        # We may be getting ';', '&&' and so forth. Adding the shell for
        # safety.
        if len(command) == 1:
            command = ["/bin/sh", "-c"] + command

        host_user = "" if jail_user and host_user == "root" else host_user
        try:
            msg = iocage.exec(
                command, host_user, jail_user, start_jail=True, msg_return=True
            )
        except Exception as e:
            raise CallError(str(e))

        return '\n'.join(msg)

    @accepts(
        Str("jail"),
        Bool("update_pkgs", default=False)
    )
    @job(lock=lambda args: f"jail_update:{args[0]}")
    def update_to_latest_patch(self, job, jail, update_pkgs=False):
        """Updates specified jail to latest patch level."""
        return self.update_to_latest_patch_internal(job, jail, update_pkgs, True)

    @private
    def update_to_latest_patch_internal(self, job, jail, update_pkgs, update_jail):
        job.set_progress(0, f'Updating {jail}')
        msg_queue = deque(maxlen=10)

        def progress_callback(content, exception):
            msg = content['message'].strip('\n')
            if 'No updates needed to update system' in msg:
                raise CallError(f'No updates available for {jail}')

            if content['level'] == 'EXCEPTION':
                raise exception(msg)

            msg_queue.append(msg)
            final_msg = '\n'.join(msg_queue)

            if 'Inspecting system... done' in msg:
                job.set_progress(20)
            elif 'Preparing to download files... done.' in msg:
                job.set_progress(50)
            elif 'Applying patches... done.' in msg:
                job.set_progress(75)
            elif 'Installing updates... done.' in msg:
                job.set_progress(90)
            elif f'{jail} has been updated successfully' in msg:
                job.set_progress(100)

            job.set_progress(None, description=final_msg)

        _, _, iocage = self.check_jail_existence(
            jail,
            callback=progress_callback
        )
        iocage.update(update_pkgs, update_jail)

        return True

    @accepts(
        Dict(
            'options',
            Str('jail', required=True),
            Str('compression_algorithm', default='ZIP', enum=['ZIP', 'LZMA'])
        )
    )
    @job(lock=lambda args: f'jail_export:{args[0]["jail"]}')
    def export(self, job, options):
        """
        Export jail to compressed file.
        """
        jail = options['jail']
        uuid, path, _ = self.check_jail_existence(jail)
        status, jid = IOCList.list_get_jid(uuid)
        started = False

        if status:
            stop_job = self.middleware.call_sync('jail.stop', jail)
            stop_job.wait_sync()
            if stop_job.error:
                raise CallError(stop_job.error)

            started = True

        IOCImage().export_jail(uuid, path, compression_algo=options['compression_algorithm'].lower())

        if started:
            start_job = self.middleware.call_sync('jail.start', jail)
            start_job.wait_sync()
            if start_job.error:
                raise CallError(start_job.error)

        return True

    @accepts(
        Dict(
            'options',
            Str('jail', required=True),
            Str('path', default=None, null=True),
            Str('compression_algorithm', default=None, null=True, enum=['ZIP', 'LZMA', None])
        )
    )
    @job(lock=lambda args: f'jail_import:{args[0]["jail"]}')
    def import_image(self, job, options):
        """
        Import jail from compressed file.

        `compression algorithm`: None indicates that middlewared is to automatically determine
        which compression algorithm to use based on the compressed file extension. If multiple copies are found, an
        exception is raised.

        `path` is the directory where the exported jail lives. It defaults to the iocage images dataset.
        """
        self.check_dataset_existence()
        path = options['path'] or os.path.join(self.get_iocroot(), 'images')

        IOCImage().import_jail(
            options['jail'], compression_algo=options['compression_algorithm'], path=path
        )

        return True

    @private
    def start_on_boot(self):
        if not self.iocage_set_up():
            return

        self.check_dataset_existence()
        self.logger.debug('Starting jails on boot: PENDING')
        ioc.IOCage(rc=True, reset_cache=True).start(ignore_exception=True)
        self.logger.debug('Starting jails on boot: SUCCESS')

        return True

    @private
    def stop_on_shutdown(self):
        if not self.iocage_set_up():
            return

        self.logger.debug('Stopping jails on shutdown: PENDING')
        ioc.IOCage(jail='ALL', reset_cache=True).stop(force=True, ignore_exception=True)
        self.logger.debug('Stopping jails on shutdown: SUCCESS')

        return True

    @private
    async def terminate(self):
        await SHUTDOWN_LOCK.acquire()


async def jail_pool_pre_lock(middleware, pool):
    """
    We need to stop jails before unlocking a pool because of used
    resources in it.
    """
    activated_pool = await middleware.call('jail.get_activated_pool')
    if activated_pool == pool['name']:
        jails = await middleware.call('jail.query', [('state', '=', 'up')])
        for j in jails:
            await middleware.call('jail.stop', j['host_hostuuid'])


async def __event_system(middleware, event_type, args):
    """
    Method called when system is ready or shutdown, supposed to start/stop jails
    flagged that way.
    """
    # We need to call a method in Jail service to make sure it runs in the
    # process pool because of py-libzfs thread safety issue with iocage and middlewared
    if args['id'] == 'ready' and await middleware.call('jail.iocage_set_up'):
        if await middleware.call('system.is_enterprise'):
            await middleware.call('jail.check_dataset_existence')
            await middleware.call('jail.update_defaults', {'nat_backend': 'ipfw'})
            # We start Jail/VM(s) during failover event
            if await middleware.call('failover.licensed'):
                return
        try:
            await middleware.call('jail.start_on_boot')
        except ioc_exceptions.PoolNotActivated:
            pass
    elif args['id'] == 'shutdown' and await middleware.call('jail.iocage_set_up'):
        async with SHUTDOWN_LOCK:
            await middleware.call('jail.stop_on_shutdown')


class JailFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'jail'
    title = 'Jail'

    async def query(self, path, enabled, options=None):
        results = []

        if not await self.middleware.call('jail.iocage_set_up'):
            return results

        query_dataset = os.path.relpath(path, '/mnt')
        try:
            activated_pool = await self.middleware.call('jail.get_activated_pool')
        except Exception:
            pass
        else:
            if not activated_pool:
                return results
            if activated_pool == query_dataset or query_dataset.startswith(os.path.join(activated_pool, 'iocage')):
                for j in await self.middleware.call('jail.query', [['OR', [('state', '=', 'up'), ('boot', '=', 1)]]]):
                    results.append({'id': j['host_hostuuid']})

        return results

    async def get_attachment_name(self, attachment):
        return attachment['id']

    async def delete(self, attachments):
        for attachment in attachments:
            try:
                await self.middleware.call('jail.stop', attachment['id'], True)
            except Exception:
                self.middleware.logger.warning('Unable to jail.stop %r', attachment['id'], exc_info=True)

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            action = 'jail.start' if enabled else 'jail.stop'
            try:
                await self.middleware.call(action, attachment['id'])
            except Exception:
                self.middleware.logger.warning('Unable to %s %r', action, attachment['id'], exc_info=True)

    async def stop(self, attachments):
        await self.toggle(attachments, False)

    async def start(self, attachments):
        await self.toggle(attachments, True)


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', JailFSAttachmentDelegate(middleware))
    await middleware.call('network.general.register_activity', 'jail', 'Plugin registry')
    middleware.register_hook('pool.pre_lock', jail_pool_pre_lock)
    middleware.event_subscribe('system', __event_system)
    ioc_common.set_interactive(False)
