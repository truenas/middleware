from middlewared.schema import (accepts, Bool, Dict, IPAddr, Int, List, Patch,
                                Str)
from middlewared.validators import Range
from middlewared.service import (CRUDService, SystemServiceService,
                                 ValidationErrors, private)
from middlewared.utils import run
from middlewared.async_validators import check_path_resides_within_volume

import bidict
import errno
import ipaddress
import re
import os

AUTHMETHOD_LEGACY_MAP = bidict.bidict({
    'None': 'NONE',
    'CHAP': 'CHAP',
    'CHAP Mutual': 'CHAP_MUTUAL',
})
RE_IP_PORT = re.compile(r'^(.+?)(:[0-9]+)?$')


class ISCSIGlobalService(SystemServiceService):

    class Config:
        datastore_extend = 'iscsi.global.config_extend'
        datastore_prefix = 'iscsi_'
        service = 'iscsitarget'
        service_model = 'iscsitargetglobalconfiguration'
        namespace = 'iscsi.global'

    @private
    def config_extend(self, data):
        data['isns_servers'] = data['isns_servers'].split()
        return data

    @accepts(Dict(
        'iscsiglobal_update',
        Str('basename'),
        List('isns_servers', items=[Str('server')]),
        Int('pool_avail_threshold', validators=[Range(min=1, max=99)]),
        Bool('alua', default=False),
    ))
    async def do_update(self, data):
        """
        `alua` is a no-op for FreeNAS.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        servers = data.get('isns_servers') or []
        for server in servers:
            reg = RE_IP_PORT.search(server)
            if reg:
                ip = reg.group(1)
                if ip and ip[0] == '[' and ip[-1] == ']':
                    ip = ip[1:-1]
                try:
                    ipaddress.ip_address(ip)
                    continue
                except ValueError:
                    pass
            verrors.add('iscsiglobal_update.isns_servers', f'Server "{server}" is not a valid IP(:PORT)? tuple.')

        if verrors:
            raise verrors

        new['isns_servers'] = '\n'.join(servers)

        await self._update_service(old, new)

        if old['alua'] != new['alua']:
            await self.middleware.call('service.start', 'ix-loader')

        return await self.config()


class ISCSIPortalService(CRUDService):

    class Config:
        datastore = 'services.iscsitargetportal'
        datastore_extend = 'iscsi.portal.config_extend'
        datastore_prefix = 'iscsi_target_portal_'
        namespace = 'iscsi.portal'

    @private
    async def config_extend(self, data):
        data['listen'] = []
        for portalip in await self.middleware.call(
            'datastore.query',
            'services.iscsitargetportalip',
            [('portal', '=', data['id'])],
            {'prefix': 'iscsi_target_portalip_'}
        ):
            data['listen'].append({
                'ip': portalip['ip'],
                'port': portalip['port'],
            })
        data['discovery_authmethod'] = AUTHMETHOD_LEGACY_MAP.get(
            data.pop('discoveryauthmethod')
        )
        data['discovery_authgroup'] = data.pop('discoveryauthgroup')
        return data

    async def __validate(self, verrors, data, schema):
        if not data['listen']:
            verrors.add(f'{schema}.listen', 'At least one listen entry is required.')
        else:
            for i in data['listen']:
                filters = [
                    ('iscsi_target_portalip_ip', '=', i['ip']),
                    ('iscsi_target_portalip_port', '=', i['port']),
                ]
                if schema == 'iscsiportal_update':
                    filters.append(('iscsi_target_portalip_portal', '!=', data['id']))
                if await self.middleware.call(
                    'datastore.query', 'services.iscsitargetportalip', filters
                ):
                    verrors.add('{schema}.listen', f'{i["ip"]}:{i["port"]} already in use.')

        if data['discovery_authgroup']:
            if not await self.middleware.call(
                'datastore.query', 'services.iscsitargetauthcredential',
                [('iscsi_target_auth_tag', '=', data['discovery_authgroup'])]
            ):
                verrors.add(
                    f'{schema}.discovery_authgroup',
                    'Auth Group "{data["discovery_authgroup"]}" not found.',
                    errno.ENOENT,
                )
        elif data['discovery_authmethod'] in ('CHAP', 'CHAP_MUTUAL'):
            verrors.add(f'{schema}.discovery_authgroup', 'This field is required if discovery method is set to CHAP or CHAP Mutual.')

    @accepts(Dict(
        'iscsiportal_create',
        Str('comment'),
        Str('discovery_authmethod', default='NONE', enum=['NONE', 'CHAP', 'CHAP_MUTUAL']),
        Int('discovery_authgroup'),
        List('listen', required=True, items=[
            Dict(
                'listen',
                IPAddr('ip', required=True),
                Int('port', default=3260, validators=[Range(min=1, max=65535)]),
            ),
        ]),
        register=True,
    ))
    async def do_create(self, data):
        """
        Create a new iSCSI Portal.

        `discovery_authgroup` is required for CHAP and CHAP_MUTUAL.
        """
        verrors = ValidationErrors()
        await self.__validate(verrors, data, 'iscsiportal_create')
        if verrors:
            raise verrors

        # tag attribute increments sequentially
        data['tag'] = (await self.middleware.call(
            'datastore.query', self._config.datastore, [], {'count': True}
        )) + 1

        listen = data.pop('listen')
        data['discoveryauthgroup'] = data.pop('discovery_authgroup', None)
        data['discoveryauthmethod'] = AUTHMETHOD_LEGACY_MAP.inv.get(data.pop('discovery_authmethod'), 'None')
        pk = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix}
        )
        try:
            await self.__save_listen(pk, listen)
        except Exception as e:
            await self.middleware.call('datastore.delete', self._config.datastore, pk)
            raise e

        await self._service_change('iscsitarget', 'reload')

        return await self._get_instance(pk)

    async def __save_listen(self, pk, new, old=None):
        """
        Update database with a set new listen IP:PORT tuples.
        It will delete no longer existing addresses and add new ones.
        """
        new_listen_set = set([tuple(i.items()) for i in new])
        old_listen_set = set([tuple(i.items()) for i in old]) if old else set()
        for i in new_listen_set - old_listen_set:
            i = dict(i)
            await self.middleware.call(
                'datastore.insert',
                'services.iscsitargetportalip',
                {'portal': pk, 'ip': i['ip'], 'port': i['port']},
                {'prefix': 'iscsi_target_portalip_'}
            )

        for i in old_listen_set - new_listen_set:
            i = dict(i)
            portalip = await self.middleware.call(
                'datastore.query',
                'services.iscsitargetportalip',
                [('portal', '=', pk), ('ip', '=', i['ip']), ('port', '=', i['port'])],
                {'prefix': 'iscsi_target_portalip_'}
            )
            if portalip:
                await self.middleware.call(
                    'datastore.delete', 'services.iscsitargetportalip', portalip[0]['id']
                )

    @accepts(
        Int('id'),
        Patch(
            'iscsiportal_create',
            'iscsiportal_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, pk, data):
        """
        Update iSCSI Portal `id`.
        """

        old = await self._get_instance(pk)

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.__validate(verrors, new, 'iscsiportal_update')
        if verrors:
            raise verrors

        listen = new.pop('listen')
        new['discoveryauthgroup'] = new.pop('discovery_authgroup', None)
        new['discoveryauthmethod'] = AUTHMETHOD_LEGACY_MAP.inv.get(new.pop('discovery_authmethod'), 'None')

        await self.__save_listen(pk, listen, old['listen'])

        await self.middleware.call(
            'datastore.update', self._config.datastore, pk, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('iscsitarget', 'reload')

        return await self._get_instance(pk)

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete iSCSI Portal `id`.
        """
        await self.middleware.call('datastore.delete', self._config.datastore, id)
        # service is currently restarted by datastore/django model


class iSCSITargetAuthCredentialService(CRUDService):
    class Config:
        namespace = 'iscsi.auth'
        datastore = 'services.iscsitargetauthcredential'
        datastore_prefix = 'iscsi_target_auth_'
        datastore_extend = 'iscsi.auth.extend'

    @accepts(Dict(
        'iscsi_auth_create',
        Int('tag'),
        Str('user'),
        Str('secret'),
        Str('peeruser'),
        Str('peersecret'),
        register=True
    ))
    async def do_create(self, data):
        verrors = ValidationErrors()
        await self.validate(data, 'iscsi_auth_create', verrors)

        if verrors:
            raise verrors

        await self.compress(data)
        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})
        await self.extend(data)
        await self.middleware.call('service.reload', 'iscsitarget')

        return data

    @accepts(
        Int('id'),
        Patch(
            'iscsi_auth_create',
            'iscsi_auth_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        verrors = ValidationErrors()
        old = await self.middleware.call(
            'datastore.query', self._config.datastore, [('id', '=', id)],
            {'extend': self._config.datastore_extend,
             'prefix': self._config.datastore_prefix,
             'get': True})

        new = old.copy()
        new.update(data)

        await self.validate(
            new, 'iscsi_auth_update', verrors)

        if verrors:
            raise verrors

        await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})
        await self.extend(new)

        await self.middleware.call('service.reload', 'iscsitarget')

        return new

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete', self._config.datastore, id)

    @private
    async def validate(self, data, schema_name, verrors):
        secret = data.get('secret', '')
        peer_secret = data.get('peersecret', '')
        peer_user = data.get('peeruser', '')

        if len(peer_user) > 0:
            if len(peer_secret) == 0:
                verrors.add(
                    f'{schema_name}.peersecret',
                    'The peer secret is required if you set a peer user.')
            elif peer_secret == secret:
                verrors.add(
                    f'{schema_name}.peersecret',
                    'The peer secret cannot be the same as user secret.')
        else:
            if len(peer_secret) > 0:
                verrors.add(
                    f'{schema_name}.peersecret',
                    'The peer secret is required if you set a peer user.')

        if len(secret) < 12 or len(secret) > 16:
            verrors.add(f'{schema_name}.secret',
                        'Secret must be between 12 and 16 characters.')

        if len(peer_secret) < 12 or len(peer_secret) > 16:
            verrors.add(f'{schema_name}.peersecret',
                        'Secret must be between 12 and 16 characters.')

    @private
    async def extend(self, data):
        secret = data.get('secret', '')
        peersecret = data.get('peersecret', '')

        data['secret'] = await self.middleware.call(
            'notifier.pwenc_decrypt', secret)
        data['peersecret'] = await self.middleware.call(
            'notifier.pwenc_decrypt', peersecret)

        return data

    @private
    async def compress(self, data):
        secret = data.get('secret', '')
        peersecret = data.get('peersecret', '')

        data['secret'] = await self.middleware.call(
            'notifier.pwenc_encrypt', secret)
        data['peersecret'] = await self.middleware.call(
            'notifier.pwenc_encrypt', peersecret)

        return data


class iSCSITargetExtentService(CRUDService):
    class Config:
        namespace = 'iscsi.extent'
        datastore = 'services.iscsitargetextent'
        datastore_prefix = 'iscsi_target_extent_'
        datastore_extend = 'iscsi.extent.extend'

    @accepts(Dict(
        'iscsi_extent_create',
        Str('name'),
        Str('type', enum=['DISK', 'FILE']),
        Str('disk', default=None),
        Str('serial', default=None),
        Str('path', default=None),
        Int('filesize', default=0),
        Int('blocksize', enum=[512, 1024, 2048, 4096], default=512),
        Bool('pblocksize'),
        Int('avail_threshold', validators=[Range(min=1, max=99)]),
        Str('comment'),
        Bool('insecure_tpc', default=True),
        Bool('xen'),
        Str('rpm', enum=['UNKNOWN', 'SSD', '5400', '7200', '10000', '15000'],
            default='SSD'),
        Bool('ro'),
        register=True
    ))
    async def do_create(self, data):
        verrors = ValidationErrors()
        await self.compress(data)
        await self.validate(data, 'iscsi_extent_create', verrors)
        await self.clean(data, 'iscsi_extent_create', verrors)

        if verrors:
            raise verrors

        await self.save(data, 'iscsi_extent_create', verrors)
        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})
        await self.extend(data)

        return data

    @accepts(
        Int('id'),
        Patch(
            'iscsi_extent_create',
            'iscsi_extent_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        verrors = ValidationErrors()
        old = await self.middleware.call(
            'datastore.query', self._config.datastore, [('id', '=', id)],
            {'extend': self._config.datastore_extend,
             'prefix': self._config.datastore_prefix,
             'get': True})

        new = old.copy()
        new.update(data)

        await self.compress(data)
        await self.validate(
            new, 'iscsi_extent_update', verrors)
        await self.clean(
            new, 'iscsi_extent_update', verrors, old=old)

        if verrors:
            raise verrors

        await self.save(data, 'iscsi_extent_update', verrors)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})
        await self.extend(data)

        return new

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete', self._config.datastore, id)

    @private
    async def validate(self, data, schema_name, verrors):
        await self.extent_serial(data['serial'])

    @private
    async def compress(self, data):
        extent_disk = data['disk']
        extent_type = data['type']
        extent_rpm = data['rpm']

        if extent_type == 'DISK':
            if extent_disk.startswith('zvol'):
                data['type'] = 'ZVOL'
            elif extent_disk.startswith('hast'):
                data['type'] = 'HAST'
            else:
                data['type'] = 'Disk'
        elif extent_type == 'FILE':
            data['type'] = 'File'

        if extent_rpm == 'UNKNOWN':
            data['rpm'] = 'Unknown'

        return data

    @private
    async def extend(self, data):
        extent_type = data['type']
        extent_rpm = data['rpm']

        if extent_type != 'File':
            # ZVOL and HAST are type DISK
            data['type'] = 'DISK'
        else:
            extent_size = data['filesize']

            # Legacy Compat for having 2[KB, MB, GB, etc] in database
            if not str(extent_size).isdigit():
                suffixes = {
                    'PB': 1125899906842624,
                    'TB': 1099511627776,
                    'GB': 1073741824,
                    'MB': 1048576,
                    'KB': 1024,
                    'B': 1
                }
                for x in suffixes.keys():
                    if extent_size.upper().endswith(x):
                        extent_size = extent_size.upper().strip(x)
                        extent_size = int(extent_size) * suffixes[x]

                        data['filesize'] = extent_size

        data['type'] = extent_type.upper()
        data['rpm'] = extent_rpm.upper()

        return data

    @private
    async def clean(self, data, schema_name, verrors, old=None):
        await self.clean_name(data, schema_name, verrors, old=old)
        await self.clean_type_and_path(data, schema_name, verrors)
        await self.clean_size(data, schema_name, verrors)

    @private
    async def clean_name(self, data, schema_name, verrors, old=None):
        name = data['name']
        old = old['name'] if old is not None else None
        serial = data['serial']
        name_filters = [('name', '=', name)]

        if '"' in name:
            verrors.add(f'{schema_name}.name', 'Double quotes are not allowed')

        if '"' in serial:
            verrors.add(f'{schema_name}.serial',
                        'Double quotes are not allowed')

        if name != old or old is None:
            name_result = await self.middleware.call(
                'datastore.query', self._config.datastore,
                name_filters,
                {'prefix': self._config.datastore_prefix})

            if name_result:
                verrors.add(f'{schema_name}.name',
                            'Extent name must be unique')

    @private
    async def clean_type_and_path(self, data, schema_name, verrors):
        extent_type = data['type']
        disk = data['disk']
        path = data['path']

        if extent_type is None:
            return data

        if extent_type == 'Disk':
            if not disk:
                verrors.add(f'{schema_name}.disk', 'This field is required')
        elif extent_type == 'ZVOL':
            if disk.startswith('zvol') and not os.path.exists(f'/dev/{disk}'):
                verrors.add(f'{schema_name}.disk',
                            f'ZVOL {disk} does not exist')
        elif extent_type == 'File':
            if not path:
                verrors.add(f'{schema_name}.path', 'This field is required')
                raise verrors  # They need this for anything else

            if '/iocage' in path:
                    verrors.add(
                        f'{schema_name}.path',
                        'You need to specify a filepath outside of a jail root'
                    )

            if (os.path.exists(path) and not
                    os.path.isfile(path)) or path[-1] == '/':
                verrors.add(f'{schema_name}.path',
                            'You need to specify a filepath not a directory')

            await check_path_resides_within_volume(verrors, self.middleware,
                                                   schema_name, path)

        return data

    @private
    async def clean_size(self, data, schema_name, verrors):
        extent_type = data['type']
        path = data['path']
        size = data['filesize']
        blocksize = data['blocksize']

        if (
            size == 0 and path and (not os.path.exists(path) or (
                os.path.exists(path) and not
                os.path.isfile(path)
            ))
        ):
            verrors.add(
                f'{schema_name}.path',
                'The file must exist if the extent size is set to auto (0)')
        elif extent_type == 'file' and not path:
            verrors.add(f'{schema_name}.path', 'This field is required')

        if size and size != 0 and blocksize:
            if (float(size) / blocksize) % 1 != 0:
                verrors.add(f'{schema_name}.filesize',
                            'File size must be a multiple of block size')

        return data

    @private
    async def extent_serial(self, serial):
        # TODO Just ported, let's do something different later? - Brandon
        if serial is None:
            try:
                nic = (await self.middleware.call('interfaces.query',
                                                  [['name', 'rnin', 'vlan'],
                                                   ['name', 'rnin', 'lagg'],
                                                   ['name', 'rnin', 'epair'],
                                                   ['name', 'rnin', 'vnet'],
                                                   ['name', 'rnin', 'bridge']])
                       )[0]
                mac = nic['link_address'].replace(':', '')

                ltg = await self.query()
                if len(ltg) > 0:
                    lid = ltg[0]['id']
                else:
                    lid = 0
                return f'{mac.strip()}{lid:02}'
            except Exception:
                return '10000001'
        else:
            return serial

    @accepts()
    async def disk_choices(self):
        diskchoices = {}
        disk_query = await self.query([('type', '=', 'Disk')])

        diskids = [i['path'] for i in disk_query]
        used_disks = [d['name'] for d in await self.middleware.call(
            'disk.query', [('identifier', 'in', diskids)])]

        zvol_query = await self.query([('type', '=', 'ZVOL')])
        used_zvols = [i['path'] for i in zvol_query]

        async for pdisk in await self.middleware.call('pool.get_disks'):
            used_disks.extend(pdisk)

        zfs_snaps = await self.middleware.call('zfs.snapshot.query', [],
                                               {'order_by': ['name']})

        zvols = await self.middleware.call('pool.dataset.query',
                                           [('type', '=', 'VOLUME')])
        for zvol in zvols:
            zvol_name = zvol['name']
            zvol_size = zvol['volsize']['value']
            if f'zvol/{zvol_name}' not in used_zvols:
                diskchoices[f'zvol/{zvol_name}'] = f'{zvol_name} ({zvol_size})'

        for snap in zfs_snaps:
            snap_name = snap['properties']['name']['value']
            snap_size = snap['properties']['referenced']['value']
            diskchoices[f'zvol/{snap_name}'] = f'{snap_name} ({snap_size})'\
                ' [ro]'

        notifier_disks = await self.middleware.call('notifier.get_disks')
        for name, disk in notifier_disks.items():
            if name in used_disks:
                continue
            size = await self.middleware.call('notifier.humanize_size',
                                              disk['capacity'])
            diskchoices[name] = f'{name} ({size})'

        return diskchoices

    @private
    async def save(self, data, schema_name, verrors):
        extent_type = data['type']
        disk = data.pop('disk', None)

        if extent_type == 'Disk':
            data['path'] = disk

            if disk.startswith('multipath'):
                self.middleware.call('notifier.unlabel_disk', disk)
                self.middleware.call('notifier.label_disk', f'extent_{disk}',
                                     disk)
            elif not disk.startswith('hast') and not disk.startswith('zvol'):
                disk_filters = [('name', '=', disk), ('expiretime', '=', None)]
                try:
                    disk_object = (await self.middleware.call('disk.query',
                                                              disk_filters))[0]
                    disk_identifier = disk_object.get('identifier', None)

                    if disk_identifier.startswith(
                        '{devicename}'or disk_identifier.startswith('{uuid}')
                    ):
                        success, msg = await self.middleware.call(
                            'notifier.label_disk', f'extent_{disk}', disk)
                        if not success:
                            verrors.add(
                                f'{schema_name}.disk',
                                f'Serial not found and glabel failed for {disk}:'
                                f' {msg}')

                            if verrors:
                                raise verrors
                        await self.middleware.call('disk.sync',
                                                   disk.replace('/dev/', ''))
                except IndexError:
                    # It's not a disk, but a ZVOL
                    pass
        elif extent_type == 'File':
            path = data['path']
            dirs = '/'.join(path.split('/')[:-1])

            if not os.path.exists(dirs):
                try:
                    os.makedirs(dirs)
                except Exception as e:
                    self.logger.error(
                        'Unable to create dirs for extent file: {e}')

            if not os.path.exists(path):
                extent_size = data['filesize']

                await run(['truncate', '-s', str(extent_size), path])

            await self.middleware.call('service.reload', 'iscsitarget')


class iSCSITargetAuthorizedInitiator(CRUDService):
    class Config:
        namespace = 'iscsi.initiator'
        datastore = 'services.iscsitargetauthorizedinitiator'
        datastore_prefix = 'iscsi_target_initiator_'
        datastore_extend = 'iscsi.initiator.extend'

    @accepts(Dict(
        'iscsi_initiator_create',
        Int('tag', default=0),
        List('initiators', default=[]),
        List('auth_network', items=[IPAddr('ip', cidr=True)], default=[]),
        Str('comment'),
        register=True
    ))
    async def do_create(self, data):
        if data['tag'] == 0:
            i = len((await self.query())) + 1
            while True:
                tag_result = await self.query([('tag', '=', i)])
                if not tag_result:
                    break
                i += 1
            data['tag'] = i

        await self.compress(data)
        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})
        await self.extend(data)
        await self.middleware.call('service.reload', 'iscsitarget')

        return data

    @accepts(
        Int('id'),
        Patch(
            'iscsi_initiator_create',
            'iscsi_initiator_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        old = await self.middleware.call(
            'datastore.query', self._config.datastore, [('id', '=', id)],
            {'extend': self._config.datastore_extend,
             'prefix': self._config.datastore_prefix,
             'get': True})

        new = old.copy()
        new.update(data)

        await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})
        await self.extend(new)

        await self.middleware.call('service.reload', 'iscsitarget')

        return new

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete', self._config.datastore, id)

    @private
    async def compress(self, data):
        initiators = data['initiators']
        auth_network = data['auth_network']

        initiators = 'ALL' if not initiators else '\n'.join(initiators)
        auth_network = 'ALL' if not auth_network else '\n'.join(auth_network)

        data['initiators'] = initiators
        data['auth_network'] = auth_network

        return data

    @private
    async def extend(self, data):
        initiators = data['initiators']
        auth_network = data['auth_network']

        initiators = [] if initiators == 'ALL' else initiators.split()
        auth_network = [] if auth_network == 'ALL' else auth_network.split()

        data['initiators'] = initiators
        data['auth_network'] = auth_network

        return data
