import asyncio
import os
import subprocess as su
import libzfs
import requests
import itertools
import tempfile
import pathlib
import json
import sqlite3
import errno

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

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.schema import Bool, Dict, Int, List, Str, accepts
from middlewared.service import CRUDService, job, private, filterable, periodic, item_method
from middlewared.service_exception import CallError, ValidationErrors
from middlewared.utils import filter_list
from middlewared.validators import IpInUse, MACAddr

from collections import deque, Iterable


SHUTDOWN_LOCK = asyncio.Lock()


class JailService(CRUDService):

    class Config:
        process_pool = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # We want debug for jails starting/stopping
        os.environ['IOCAGE_DEBUG'] = 'TRUE'

    @filterable
    def query(self, filters=None, options=None):
        """
        Query all jails with `query-filters` and `query-options`.
        """
        options = options or {}
        jail_identifier = None
        jails = []

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
                    if jail['dhcp'] == 'on':
                        uuid = jail['host_hostuuid']

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

                    if jail['state'] == 'up':
                        try:
                            jail['jid'] = su.check_output(
                                [
                                    'jls', '-j',
                                    f'ioc-{jail["host_hostuuid"]}',
                                    'jid'
                                ]
                            ).decode().strip()
                        except su.CalledProcessError:
                            jail['jid'] = 'ERROR'
                    else:
                        jail['jid'] = None

                    jails.append(jail)
        except ioc_exceptions.JailMisconfigured as e:
            self.logger.error(e, exc_info=True)
        except BaseException:
            # Brandon is working on fixing this generic except, till then I
            # am not going to make the perfect the enemy of the good enough!
            self.logger.debug('Failed to get list of jails', exc_info=True)

        return filter_list(jails, filters, options)

    @accepts(
        Dict(
            "options",
            Str("release", required=True),
            Str("template"),
            List("pkglist", default=[], items=[Str("pkg", empty=False)]),
            Str("uuid", required=True),
            Bool("basejail", default=False),
            Bool("empty", default=False),
            Bool("short", default=False),
            List("props", default=[]),
            Bool('https', default=True)
        )
    )
    async def do_create(self, options):
        """Creates a jail."""
        # Typically one would return the created jail's id in this
        # create call BUT since jail creation may or may not involve
        # fetching a release, which in turn could be time consuming
        # and could then block for a long time. This dictates that we
        # make it a job, but that violates the principle that CRUD methods
        # are not jobs as yet, so I settle on making this a wrapper around
        # the main job that calls this and return said job's id instead of
        # the created jail's id

        return await self.middleware.call('jail.create_job', options)

    @private
    @job(lock=lambda args: f'jail_create:{args[-1]["uuid"]}')
    def create_job(self, job, options):
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

            verrors = self.common_validation(verrors, options)

            if verrors:
                raise verrors

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
            self.middleware.call_sync(
                'jail.fetch', {"release": release, "https": https}, job=True
            )

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

        return True

    @item_method
    @accepts(
        Str('source_jail', empty=False),
        Dict(
            'clone_jail',
            Str('uuid', required=True, empty=False),
            List('pkglist', default=[], items=[Str('pkg', empty=False)]),
            Bool('thickjail', default=False),
            List('props', default=[]),
        )
    )
    @job(lock=lambda args: f'clone_jail:{args[-2]}')
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
        verrors = self.common_validation(verrors, options)
        verrors.check()

        job.set_progress(25, 'Initial validation complete.')

        ioc.IOCage(jail=source_jail, skip_jails=True).create(
            source_jail, options['props'], _uuid=options['uuid'], thickjail=options['thickjail'], clone=True
        )

        job.set_progress(100, 'Jail has been successfully cloned.')

        return self.middleware.call_sync('jail._get_instance', options['uuid'])

    @private
    def validate_ips(self, verrors, options, schema='options.props', exclude=None):
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
                            IpInUse(self.middleware, exclude)(
                                ip
                            )
                        except ValueError as e:
                            verrors.add(
                                f'{schema}.{f}',
                                str(e)
                            )

    @accepts(Str("jail"), Dict(
             "options",
             Bool("plugin", default=False),
             additional_attrs=True,
             ))
    def do_update(self, jail, options):
        """Sets a jail property."""
        plugin = options.pop("plugin")
        _, _, iocage = self.check_jail_existence(jail)

        name = options.pop("name", None)

        verrors = ValidationErrors()

        jail = self.query([['id', '=', jail]], {'get': True})

        verrors = self.common_validation(verrors, options, True, jail)

        if name is not None and plugin:
            verrors.add('options.plugin',
                        'Cannot be true while trying to rename')

        if verrors:
            raise verrors

        for prop, val in options.items():
            p = f"{prop}={val}"

            try:
                iocage.set(p, plugin)
            except RuntimeError as err:
                raise CallError(err)

        if name:
            iocage.rename(name)

        return True

    @private
    def common_validation(self, verrors, options, update=False, jail=None):
        if not update:
            # Ensure that api call conforms to format set by iocage for props
            # Example 'key=value'

            for value in options['props']:
                if '=' not in value:
                    verrors.add(
                        'options.props',
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

            self.validate_ips(verrors, options)
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

            self.validate_ips(
                verrors, {'props': [f'{k}={v}' for k, v in options.items()]},
                'options', exclude_ips
            )

        # validate vnetX_mac addresses
        for key, value in vnet_macs.items():
            if value and value != 'none':
                value = value.replace(',', ' ')
                try:
                    for mac in value.split():
                        MACAddr()(mac)

                    if (
                        len(value.split()) != 2 or
                        any(value.split().count(v) > 1 for v in value.split())
                    ):
                        raise ValueError('Exception')
                except ValueError:
                    verrors.add(
                        key,
                        'Please Enter two valid and different '
                        f'space/comma-delimited MAC addresses for {key}.'
                    )

        return verrors

    @accepts(Str("jail"))
    def do_delete(self, jail):
        """Takes a jail and destroys it."""
        _, _, iocage = self.check_jail_existence(jail)

        # TODO: Port children checking, release destroying.
        iocage.destroy_jail()

        return True

    @private
    def check_dataset_existence(self):
        try:
            IOCCheck(migrate=True)
        except ioc_exceptions.PoolNotActivated as e:
            raise CallError(e, errno=errno.ENOENT)

    @private
    def check_jail_existence(self, jail, skip=True, callback=None):
        """Wrapper for iocage's API, as a few commands aren't ported to it"""
        try:
            if callback is not None:
                iocage = ioc.IOCage(callback=callback,
                                    skip_jails=skip, jail=jail)
            else:
                iocage = ioc.IOCage(skip_jails=skip, jail=jail)
            jail, path = iocage.__check_jail_existence__()
        except (SystemExit, RuntimeError):
            raise CallError(f"jail '{jail}' not found!")

        return jail, path, iocage

    @accepts()
    def get_activated_pool(self):
        """Returns the activated pool if there is one, or None"""
        try:
            pool = ioc.IOCage(skip_jails=True).get('', pool=True)
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

    @accepts(
        Dict(
            'options',
            Str('release'),
            Str('server', default='download.freebsd.org'),
            Str('user', default='anonymous'),
            Str('password', default='anonymous@'),
            Str('name', default=None, null=True),
            Str('jail_name', default=None, null=True),
            Bool('accept', default=True),
            Bool('https', default=True),
            List('props', default=[]),
            List(
                'files',
                default=['MANIFEST', 'base.txz', 'lib32.txz', 'doc.txz']
            ),
            Str('branch', default=None, null=True)
        )
    )
    @job(lock=lambda args: f"jail_fetch:{args[-1]}")
    def fetch(self, job, options):
        """Fetches a release or plugin."""
        fetch_output = {'install_notes': []}
        release = options.get('release', None)
        https = options.pop('https', False)
        name = options.pop('name')
        jail_name = options.pop('jail_name')

        post_install = False

        verrors = ValidationErrors()

        self.validate_ips(verrors, options)

        if verrors:
            raise verrors

        def progress_callback(content, exception):
            msg = content['message'].strip('\r\n')
            rel_up = f'* Updating {release} to the latest patch level... '
            nonlocal post_install

            if name is None:
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
            else:
                if post_install:
                    for split_msg in msg.split('\n'):
                        fetch_output['install_notes'].append(split_msg)

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

        self.check_dataset_existence()  # Make sure our datasets exist.
        start_msg = f'{release} being fetched'
        final_msg = f'{release} fetched'

        iocage = ioc.IOCage(callback=progress_callback, silent=False)

        if name is not None:
            pool = IOCJson().json_get_value('pool')
            iocroot = IOCJson(pool).json_get_value('iocroot')

            options["plugin_name"] = name
            start_msg = 'Starting plugin install'
            final_msg = f"Plugin: {name} installed"
        elif name is None and https:
            if 'https' not in options['server']:
                options['server'] = f'https://{options["server"]}'

        options["accept"] = True
        options['name'] = jail_name

        job.set_progress(0, start_msg)
        iocage.fetch(**options)

        if post_install and name is not None:
            plugin_manifest = pathlib.Path(
                f'{iocroot}/.plugin_index/{name}.json'
            )
            plugin_json = json.loads(plugin_manifest.read_text())
            schema_version = plugin_json.get('plugin_schema', '1')

            if schema_version.isdigit() and int(schema_version) >= 2:
                plugin_output = pathlib.Path(
                    f'{iocroot}/jails/{name}/root/root/PLUGIN_INFO'
                )

                if plugin_output.is_file():
                    # Otherwise it will be the verbose output from the
                    # post_install script
                    fetch_output['install_notes'] = [
                        x for x in plugin_output.read_text().split('\n') if x
                    ]

                    # This is to get the admin URL and such
                    fetch_output['install_notes'] += job.progress[
                        'description'].split('\n')

        job.set_progress(100, final_msg)

        return fetch_output

    @accepts(
        Str('resource', enum=['RELEASE', 'TEMPLATE', 'PLUGIN', 'BRANCHES']),
        Bool('remote', default=False),
        Bool('want_cache', default=True),
        Str('branch', default=None)
    )
    @job(lock=lambda args: args[0])
    def list_resource(self, job, resource, remote, want_cache, branch):
        """Returns a JSON list of the supplied resource on the host"""
        self.check_dataset_existence()  # Make sure our datasets exist.
        iocage = ioc.IOCage(skip_jails=True)
        resource = "base" if resource == "RELEASE" else resource.lower()

        if resource == "plugin":
            if remote:
                if want_cache:
                    try:
                        resource_list = self.middleware.call_sync(
                            'cache.get', 'iocage_remote_plugins')

                        return resource_list
                    except KeyError:
                        pass

                resource_list = iocage.fetch(list=True, plugins=True, header=False, branch=branch)
                try:
                    plugins_versions_data = self.middleware.call_sync('cache.get', 'iocage_plugin_versions')
                except KeyError:
                    plugins_versions_data_job = self.middleware.call_sync(
                        'core.get_jobs',
                        [['method', '=', 'jail.retrieve_plugin_versions'], ['state', '=', 'RUNNING']]
                    )
                    error = None
                    plugins_versions_data = {}
                    if plugins_versions_data_job:
                        try:
                            plugins_versions_data = self.middleware.call_sync(
                                'core.job_wait', plugins_versions_data_job[0]['id'], job=True
                            )
                        except CallError as e:
                            error = str(e)
                    else:
                        try:
                            plugins_versions_data = self.middleware.call_sync(
                                'jail.retrieve_plugin_versions', job=True
                            )
                        except Exception as e:
                            error = e

                    if error:
                        # Let's not make the failure fatal
                        self.middleware.logger.error(f'Retrieving plugins version failed: {error}')
            else:
                resource_list = iocage.list("all", plugin=True)
                pool = IOCJson().json_get_value("pool")
                iocroot = IOCJson(pool).json_get_value("iocroot")
                index_path = f'{iocroot}/.plugin_index/INDEX'
                plugin_jails = {
                    j['host_hostuuid']: j for j in self.middleware.call_sync(
                        'jail.query', [['type', 'in', ['plugin', 'pluginv2']]]
                    )
                }

                if not pathlib.Path(index_path).is_file():
                    index_json = None
                else:
                    index_fd = open(index_path, 'r')
                    index_json = json.load(index_fd)

            for index, plugin in enumerate(resource_list):

                if remote:
                    # In case of remote, "plugin" is going to be a dictionary
                    plugin.update({
                        k: plugins_versions_data.get(plugin['plugin'], {}).get(k, 'N/A')
                        for k in ('version', 'revision', 'epoch')
                    })
                else:
                    # "plugin" is a list which we will convert to a dictionary for readability
                    plugin_dict = {
                        k: v if v != '-' else None
                        for k, v in zip((
                            'jid', 'name', 'boot', 'state', 'type', 'release', 'ip4', 'ip6', 'template', 'admin_portal'
                        ), plugin)
                    }
                    plugin_output = pathlib.Path(
                        f'{iocroot}/jails/{plugin[1]}/root/root/PLUGIN_INFO'
                    )

                    if plugin_output.is_file():
                        plugin_info = [[
                            x for x in plugin_output.read_text().split(
                                '\n') if x
                        ]]
                    else:
                        plugin_info = None

                    plugin_name = plugin_jails[plugin_dict['name']]['plugin_name']
                    plugin_dict.update({
                        'plugin_info': plugin_info,
                        'plugin': plugin_name if plugin_name != 'none' else plugin_dict['name'],
                        **self.get_local_plugin_version(
                            plugin_name if plugin_name != 'none' else plugin_dict['name'],
                            index_json, iocroot, plugin_dict['name']
                        )
                    })

                    resource_list[index] = plugin_dict

            if remote:
                self.middleware.call_sync(
                    'cache.put', 'iocage_remote_plugins', resource_list,
                    86400
                )
            else:
                index_fd.close()
        elif resource == "base":
            try:
                if remote:
                    resource_list = self.middleware.call_sync(
                        'cache.get', 'iocage_remote_releases')

                    return resource_list
            except KeyError:
                pass

            resource_list = iocage.fetch(list=True, remote=remote, http=True)

            if remote:
                self.middleware.call_sync(
                    'cache.put', 'iocage_remote_releases', resource_list,
                    86400
                )
        elif resource == 'branches':
            official_branches = requests.get(
                'https://api.github.com/repos/freenas/iocage-ix-plugins/'
                'branches'
            )
            official_branches.raise_for_status()
            resource_list = [
                {'name': b['name'], 'repo': 'official'}
                for b in official_branches.json()
            ]
        else:
            resource_list = [
                {k: v if v != '-' else None for k, v in zip(('jid', 'name', 'state', 'release', 'ip4'), jail_data)}
                for jail_data in iocage.list(resource)
            ]

        return resource_list

    @periodic(interval=86400)
    @private
    @accepts(Str('branch', null=True, default=None))
    @job(lock='retrieve_plugin_versions')
    def retrieve_plugin_versions(self, job, branch=None):
        branch = branch or self.get_version()
        try:
            pool = self.get_activated_pool()
        except CallError:
            pool = None

        if pool:
            plugins = IOCPlugin(branch=branch).fetch_plugin_versions()
        else:
            with tempfile.TemporaryDirectory() as td:
                github_repo = 'https://github.com/freenas/iocage-ix-plugins.git'
                try:
                    IOCPlugin._clone_repo(branch, github_repo, td, depth=1)
                except Exception:
                    self.middleware.logger.error('Failed to clone iocage-ix-plugins repository.', exc_info=True)
                    return {}
                else:
                    plugins_index_data = IOCPlugin.retrieve_plugin_index_data(td)
                    plugins = IOCPlugin.fetch_plugin_versions_from_plugin_index(plugins_index_data)

        self.middleware.call_sync('cache.put', 'iocage_plugin_versions', plugins)
        return plugins

    @accepts(Str("action", enum=["START", "STOP", "RESTART"]))
    def rc_action(self, action):
        """Does specified action on rc enabled (boot=on) jails"""
        iocage = ioc.IOCage(rc=True)

        try:
            if action == "START":
                iocage.start()
            elif action == "STOP":
                iocage.stop()
            else:
                iocage.restart()
        except BaseException as e:
            raise CallError(str(e))

        return True

    @accepts(Str('jail'))
    @job(lock=lambda args: f'jail_start:{args[-1]}')
    def start(self, job, jail):
        """Takes a jail and starts it."""
        uuid, _, iocage = self.check_jail_existence(jail)
        status, _ = IOCList.list_get_jid(uuid)

        if not status:
            try:
                iocage.start()
            except BaseException as e:
                raise CallError(str(e))

        return True

    @accepts(Str("jail"), Bool('force', default=False))
    @job(lock=lambda args: f'jail_stop:{args[-1]}')
    def stop(self, job, jail, force):
        """Takes a jail and stops it."""
        uuid, _, iocage = self.check_jail_existence(jail)
        status, _ = IOCList.list_get_jid(uuid)

        if status:
            try:
                iocage.stop(force=force)
            except BaseException as e:
                raise CallError(str(e))

            return True

    @accepts(Str('jail'))
    @job(lock=lambda args: f"jail_restart:{args[-1]}")
    def restart(self, job, jail):
        """Takes a jail and restarts it."""
        uuid, _, iocage = self.check_jail_existence(jail)
        status, _ = IOCList.list_get_jid(uuid)

        if status:
            try:
                iocage.stop()
            except BaseException as e:
                raise CallError(str(e))

        try:
            iocage.start()
        except BaseException as e:
            raise CallError(str(e))

        return True

    @private
    def get_iocroot(self):
        pool = IOCJson().json_get_value("pool")
        return IOCJson(pool).json_get_value("iocroot")

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
                fstab_entry = i[1].split()
                _fstab_type = 'SYSTEM' if fstab_entry[0].endswith(
                    system_mounts) else 'USER'

                split_list[i[0]] = {'entry': fstab_entry, 'type': _fstab_type}

            return split_list

        return True

    @accepts(Str("pool"))
    def activate(self, pool):
        """Activates a pool for iocage usage, and deactivates the rest."""
        zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
        pools = zfs.pools
        prop = "org.freebsd.ioc:active"
        activated = False

        for _pool in pools:
            if _pool.name == pool:
                ds = zfs.get_dataset(_pool.name)
                ds.properties[prop] = libzfs.ZFSUserProperty("yes")
                activated = True
            else:
                ds = zfs.get_dataset(_pool.name)
                ds.properties[prop] = libzfs.ZFSUserProperty("no")

        return activated

    @accepts(Str("ds_type", enum=["ALL", "JAIL", "TEMPLATE", "RELEASE"]))
    def clean(self, ds_type):
        """Cleans all iocage datasets of ds_type"""

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
    @job(lock=lambda args: f"jail_exec:{args[-1]}")
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
        except BaseException as e:
            raise CallError(str(e))

        return '\n'.join(msg)

    @accepts(
        Str("jail"),
        Bool("update_pkgs", default=False)
    )
    @job(lock=lambda args: f"jail_update:{args[-2]}")
    def update_to_latest_patch(self, job, jail, update_pkgs=False):
        """Updates specified jail to latest patch level."""
        job.set_progress(0, f'Updating {jail}')
        msg_queue = deque(maxlen=10)

        def progress_callback(content, exception):
            msg = content['message'].strip('\n')
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
        iocage.update(update_pkgs)

        return True

    @accepts(
        Str("jail"),
        Dict("options",
             Str("release", required=False),
             Bool("plugin", default=False))
    )
    @job(lock=lambda args: f"jail_upgrade:{args[-1]}")
    def upgrade(self, job, jail, options):
        """Upgrades specified jail to specified RELEASE."""
        verrors = ValidationErrors()
        release = options.get('release', None)
        plugin = options['plugin']

        if release is None and not plugin:
            verrors.add(
                'options.release',
                'Must not be None if options.plugin is False.'
            )
            raise verrors

        job.set_progress(0, f'Upgrading {jail}')
        msg_queue = deque(maxlen=10)

        def progress_callback(content, exception):
            msg = content['message'].strip('\n')
            msg_queue.append(msg)
            final_msg = '\n'.join(msg_queue)

            if plugin:
                plugin_progress(job, msg)
            else:
                jail_progress(job, msg)

            job.set_progress(None, description=final_msg)

        def plugin_progress(job, msg):
            if 'Snapshotting' in msg:
                job.set_progress(20)
            elif 'Updating plugin INDEX' in msg:
                job.set_progress(40)
            elif 'Running upgrade' in msg:
                job.set_progress(70)
            elif 'Installing plugin packages' in msg:
                job.set_progress(90)
            elif f'{jail} successfully upgraded' in msg:
                job.set_progress(100)

        def jail_progress(job, msg):
            if 'Inspecting system' in msg:
                job.set_progress(20)
            elif 'Preparing to download files' in msg:
                job.set_progress(50)
            elif 'Applying patches' in msg:
                job.set_progress(75)
            elif 'Installing updates' in msg:
                job.set_progress(90)
            elif f'{jail} successfully upgraded' in msg:
                job.set_progress(100)

        _, _, iocage = self.check_jail_existence(
            jail,
            callback=progress_callback
        )
        iocage.upgrade(release=release)

        return True

    @accepts(Str("jail"))
    @job(lock=lambda args: f"jail_export:{args[-1]}")
    def export(self, job, jail):
        """Exports jail to zip file"""
        uuid, path, _ = self.check_jail_existence(jail)
        status, jid = IOCList.list_get_jid(uuid)
        started = False

        if status:
            self.middleware.call_sync('jail.stop', jail, job=True)
            started = True

        IOCImage().export_jail(uuid, path)

        if started:
            self.middleware.call_sync('jail.start', jail, job=True)

        return True

    @accepts(Str("jail"))
    @job(lock=lambda args: f"jail_import:{args[-1]}")
    def _import(self, job, jail):
        """Imports jail from zip file"""

        IOCImage().import_jail(jail)

        return True

    @private
    def get_local_plugin_version(self, plugin, index_json, iocroot, jail_name):
        """
        Checks the primary_pkg key in the INDEX with the pkg version
        inside the jail.
        """
        version = {k: 'N/A' for k in ('version', 'revision', 'epoch')}

        if index_json is None:
            return version

        try:
            base_plugin = plugin.rsplit('_', 1)[0]  # May have multiple
            primary_pkg = index_json[base_plugin].get('primary_pkg') or plugin

            # Since these are plugins, we don't want to spin them up just to
            # check a pkg, directly accessing the db is best in this case.
            db_rows = self.read_plugin_pkg_db(
                f'{iocroot}/jails/{jail_name}/root/var/db/pkg/local.sqlite',
                primary_pkg)

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
            raise CallError(e)

        with conn:
            cur = conn.cursor()
            cur.execute(
                f'SELECT * FROM packages WHERE origin="{pkg}" OR name="{pkg}"'
            )

            rows = cur.fetchall()

            return rows

    @private
    def start_on_boot(self):
        self.logger.debug('Starting jails on boot: PENDING')
        ioc.IOCage(rc=True).start()
        self.logger.debug('Starting jails on boot: SUCCESS')

        return True

    @private
    def stop_on_shutdown(self):
        self.logger.debug('Stopping jails on shutdown: PENDING')
        ioc.IOCage(rc=True).stop()
        self.logger.debug('Stopping jails on shutdown: SUCCESS')

        return True

    @private
    async def terminate(self):
        await SHUTDOWN_LOCK.acquire()

    @private
    def get_version(self):
        """
        Uses system.version and parses it out for the RELEASE branch we need
        """
        r = os.uname().release
        version = f'{round(float(r.split("-")[0]), 1)}-RELEASE'

        return version


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
    if args['id'] == 'ready':
        try:
            await middleware.call('jail.start_on_boot')
        except ioc_exceptions.PoolNotActivated:
            pass
    elif args['id'] == 'shutdown':
        async with SHUTDOWN_LOCK:
            await middleware.call('jail.stop_on_shutdown')


class JailFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'jail'
    title = 'Jail'

    async def query(self, path, enabled):
        results = []
        pool_name = os.path.relpath(path, '/mnt').split('/')[0]
        try:
            activated_pool = await self.middleware.call('jail.get_activated_pool')
        except Exception:
            pass
        else:
            if activated_pool == pool_name:
                for j in await self.middleware.call('jail.query', [('state', '=', 'up')]):
                    results.append({'id': j['host_hostuuid']})

        return results

    async def get_attachment_name(self, attachment):
        return attachment['id']

    async def delete(self, attachments):
        for attachment in attachments:
            try:
                await self.middleware.call('jail.stop', attachment['id'])
            except Exception:
                self.middleware.logger.warning('Unable to jail.stop %r', attachment['id'], exc_info=True)

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            action = 'jail.start' if enabled else 'jail.stop'
            try:
                await self.middleware.call(action, attachment['id'])
            except Exception:
                self.middleware.logger.warning('Unable to %s %r', action, attachment['id'], exc_info=True)


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', JailFSAttachmentDelegate(middleware))
    middleware.register_hook('pool.pre_lock', jail_pool_pre_lock)
    middleware.event_subscribe('system', __event_system)
