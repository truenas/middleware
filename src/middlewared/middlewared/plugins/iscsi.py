from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.zfs_.utils import zvol_name_to_path
from middlewared.schema import (accepts, Bool, Dict, IPAddr, Int, List, Patch,
                                Str)
from middlewared.service import CallError, CRUDService, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.utils.path import is_child

import bidict
import errno
import re
import os
try:
    import sysctl
except ImportError:
    sysctl = None

AUTHMETHOD_LEGACY_MAP = bidict.bidict({
    'None': 'NONE',
    'CHAP': 'CHAP',
    'CHAP Mutual': 'CHAP_MUTUAL',
})
RE_TARGET_NAME = re.compile(r'^[-a-z0-9\.:]+$')


class iSCSITargetAuthorizedInitiatorModel(sa.Model):
    __tablename__ = 'services_iscsitargetauthorizedinitiator'

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_target_initiator_initiators = sa.Column(sa.Text(), default="ALL")
    iscsi_target_initiator_auth_network = sa.Column(sa.Text(), default="ALL")
    iscsi_target_initiator_comment = sa.Column(sa.String(120))


class iSCSITargetAuthorizedInitiator(CRUDService):

    class Config:
        namespace = 'iscsi.initiator'
        datastore = 'services.iscsitargetauthorizedinitiator'
        datastore_prefix = 'iscsi_target_initiator_'
        datastore_extend = 'iscsi.initiator.extend'
        cli_namespace = 'sharing.iscsi.target.authorized_initiator'

    @accepts(Dict(
        'iscsi_initiator_create',
        List('initiators'),
        List('auth_network', items=[IPAddr('ip', network=True)]),
        Str('comment'),
        register=True
    ))
    async def do_create(self, data):
        """
        Create an iSCSI Initiator.

        `initiators` is a list of initiator hostnames which are authorized to access an iSCSI Target. To allow all
        possible initiators, `initiators` can be left empty.

        `auth_network` is a list of IP/CIDR addresses which are allowed to use this initiator. If all networks are
        to be allowed, this field should be left empty.
        """
        await self.compress(data)

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(data['id'])

    @accepts(
        Int('id'),
        Patch(
            'iscsi_initiator_create',
            'iscsi_initiator_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        """
        Update iSCSI initiator of `id`.
        """
        old = await self.get_instance(id)

        new = old.copy()
        new.update(data)

        await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(id)

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete iSCSI initiator of `id`.
        """
        await self.get_instance(id)
        result = await self.middleware.call(
            'datastore.delete', self._config.datastore, id
        )

        await self._service_change('iscsitarget', 'reload')

        return result

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


class iSCSITargetModel(sa.Model):
    __tablename__ = 'services_iscsitarget'

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_target_name = sa.Column(sa.String(120), unique=True)
    iscsi_target_alias = sa.Column(sa.String(120), nullable=True, unique=True)
    iscsi_target_mode = sa.Column(sa.String(20), default='iscsi')


class iSCSITargetGroupModel(sa.Model):
    __tablename__ = 'services_iscsitargetgroups'
    __table_args__ = (
        sa.Index(
            'services_iscsitargetgroups_iscsi_target_id__iscsi_target_portalgroup_id',
            'iscsi_target_id', 'iscsi_target_portalgroup_id',
            unique=True
        ),
    )

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_target_id = sa.Column(sa.ForeignKey('services_iscsitarget.id'), index=True)
    iscsi_target_portalgroup_id = sa.Column(sa.ForeignKey('services_iscsitargetportal.id'), index=True)
    iscsi_target_initiatorgroup_id = sa.Column(sa.ForeignKey('services_iscsitargetauthorizedinitiator.id',
                                                             ondelete='SET NULL'), index=True, nullable=True)
    iscsi_target_authtype = sa.Column(sa.String(120), default="None")
    iscsi_target_authgroup = sa.Column(sa.Integer(), nullable=True)
    iscsi_target_initialdigest = sa.Column(sa.String(120), default="Auto")


class iSCSITargetService(CRUDService):

    class Config:
        namespace = 'iscsi.target'
        datastore = 'services.iscsitarget'
        datastore_prefix = 'iscsi_target_'
        datastore_extend = 'iscsi.target.extend'
        cli_namespace = 'sharing.iscsi.target'

    @private
    async def extend(self, data):
        data['mode'] = data['mode'].upper()
        data['groups'] = await self.middleware.call(
            'datastore.query',
            'services.iscsitargetgroups',
            [('iscsi_target', '=', data['id'])],
        )
        for group in data['groups']:
            group.pop('id')
            group.pop('iscsi_target')
            group.pop('iscsi_target_initialdigest')
            for i in ('portal', 'initiator'):
                val = group.pop(f'iscsi_target_{i}group')
                if val:
                    val = val['id']
                group[i] = val
            group['auth'] = group.pop('iscsi_target_authgroup')
            group['authmethod'] = AUTHMETHOD_LEGACY_MAP.get(
                group.pop('iscsi_target_authtype')
            )
        return data

    @accepts(Dict(
        'iscsi_target_create',
        Str('name', required=True),
        Str('alias', null=True),
        Str('mode', enum=['ISCSI', 'FC', 'BOTH'], default='ISCSI'),
        List('groups', items=[
            Dict(
                'group',
                Int('portal', required=True),
                Int('initiator', default=None, null=True),
                Str('authmethod', enum=['NONE', 'CHAP', 'CHAP_MUTUAL'], default='NONE'),
                Int('auth', default=None, null=True),
            ),
        ]),
        register=True
    ))
    async def do_create(self, data):
        """
        Create an iSCSI Target.

        `groups` is a list of group dictionaries which provide information related to using a `portal`, `initiator`,
        `authmethod` and `auth` with this target. `auth` represents a valid iSCSI Authorized Access and defaults to
        null.
        """
        verrors = ValidationErrors()
        await self.__validate(verrors, data, 'iscsi_target_create')
        if verrors:
            raise verrors

        await self.compress(data)
        groups = data.pop('groups')
        pk = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})
        try:
            await self.__save_groups(pk, groups)
        except Exception as e:
            await self.middleware.call('datastore.delete', self._config.datastore, pk)
            raise e

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(pk)

    async def __save_groups(self, pk, new, old=None):
        """
        Update database with a set of new target groups.
        It will delete no longer existing groups and add new ones.
        """
        new_set = set([tuple(i.items()) for i in new])
        old_set = set([tuple(i.items()) for i in old]) if old else set()

        for i in old_set - new_set:
            i = dict(i)
            targetgroup = await self.middleware.call(
                'datastore.query',
                'services.iscsitargetgroups',
                [
                    ('iscsi_target', '=', pk),
                    ('iscsi_target_portalgroup', '=', i['portal']),
                    ('iscsi_target_initiatorgroup', '=', i['initiator']),
                    ('iscsi_target_authtype', '=', i['authmethod']),
                    ('iscsi_target_authgroup', '=', i['auth']),
                ],
            )
            if targetgroup:
                await self.middleware.call(
                    'datastore.delete', 'services.iscsitargetgroups', targetgroup[0]['id']
                )

        for i in new_set - old_set:
            i = dict(i)
            await self.middleware.call(
                'datastore.insert',
                'services.iscsitargetgroups',
                {
                    'iscsi_target': pk,
                    'iscsi_target_portalgroup': i['portal'],
                    'iscsi_target_initiatorgroup': i['initiator'],
                    'iscsi_target_authtype': i['authmethod'],
                    'iscsi_target_authgroup': i['auth'],
                },
            )

    async def __validate(self, verrors, data, schema_name, old=None):

        if not RE_TARGET_NAME.search(data['name']):
            verrors.add(
                f'{schema_name}.name',
                'Lowercase alphanumeric characters plus dot (.), dash (-), and colon (:) are allowed.'
            )
        else:
            filters = [('name', '=', data['name'])]
            if old:
                filters.append(('id', '!=', old['id']))
            names = await self.middleware.call(f'{self._config.namespace}.query', filters, {'force_sql_filters': True})
            if names:
                verrors.add(f'{schema_name}.name', 'Target name already exists')

        if data.get('alias') is not None:
            if '"' in data['alias']:
                verrors.add(f'{schema_name}.alias', 'Double quotes are not allowed')
            elif data['alias'] == 'target':
                verrors.add(f'{schema_name}.alias', 'target is a reserved word')
            else:
                filters = [('alias', '=', data['alias'])]
                if old:
                    filters.append(('id', '!=', old['id']))
                aliases = await self.middleware.call(f'{self._config.namespace}.query', filters, {'force_sql_filters': True})
                if aliases:
                    verrors.add(f'{schema_name}.alias', 'Alias already exists')

        if (
            data['mode'] != 'ISCSI' and
            not await self.middleware.call('system.feature_enabled', 'FIBRECHANNEL')
        ):
            verrors.add(f'{schema_name}.mode', 'Fibre Channel not enabled')

        # Creating target without groups should be allowed for API 1.0 compat
        # if not data['groups']:
        #    verrors.add(f'{schema_name}.groups', 'At least one group is required')

        db_portals = list(
            map(
                lambda v: v['id'],
                await self.middleware.call('datastore.query', 'services.iSCSITargetPortal', [
                    ['id', 'in', list(map(lambda v: v['portal'], data['groups']))]
                ])
            )
        )

        db_initiators = list(
            map(
                lambda v: v['id'],
                await self.middleware.call('datastore.query', 'services.iSCSITargetAuthorizedInitiator', [
                    ['id', 'in', list(map(lambda v: v['initiator'], data['groups']))]
                ])
            )
        )

        portals = []
        for i, group in enumerate(data['groups']):
            if group['portal'] in portals:
                verrors.add(f'{schema_name}.groups.{i}.portal', f'Portal {group["portal"]} cannot be '
                                                                'duplicated on a target')
            elif group['portal'] not in db_portals:
                verrors.add(
                    f'{schema_name}.groups.{i}.portal',
                    f'{group["portal"]} Portal not found in database'
                )
            else:
                portals.append(group['portal'])

            if group['initiator'] and group['initiator'] not in db_initiators:
                verrors.add(
                    f'{schema_name}.groups.{i}.initiator',
                    f'{group["initiator"]} Initiator not found in database'
                )

            if not group['auth'] and group['authmethod'] in ('CHAP', 'CHAP_MUTUAL'):
                verrors.add(f'{schema_name}.groups.{i}.auth', 'Authentication group is required for '
                                                              'CHAP and CHAP Mutual')
            elif group['auth'] and group['authmethod'] == 'CHAP_MUTUAL':
                auth = await self.middleware.call('iscsi.auth.query', [('tag', '=', group['auth'])])
                if not auth:
                    verrors.add(f'{schema_name}.groups.{i}.auth', 'Authentication group not found', errno.ENOENT)
                else:
                    if not auth[0]['peeruser']:
                        verrors.add(f'{schema_name}.groups.{i}.auth', f'Authentication group {group["auth"]} '
                                                                      'does not support CHAP Mutual')

    @accepts(
        Int('id'),
        Patch(
            'iscsi_target_create',
            'iscsi_target_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        """
        Update iSCSI Target of `id`.
        """
        old = await self.get_instance(id)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.__validate(verrors, new, 'iscsi_target_create', old=old)
        if verrors:
            raise verrors

        await self.compress(new)
        groups = new.pop('groups')

        oldgroups = old.copy()
        await self.compress(oldgroups)
        oldgroups = oldgroups['groups']

        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.__save_groups(id, groups, oldgroups)

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(id)

    @accepts(Int('id'), Bool('force', default=False))
    async def do_delete(self, id, force):
        """
        Delete iSCSI Target of `id`.

        Deleting an iSCSI Target makes sure we delete all Associated Targets which use `id` iSCSI Target.
        """
        target = await self.get_instance(id)
        if await self.active_sessions_for_targets([target['id']]):
            if force:
                self.middleware.logger.warning('Target %s is in use.', target['name'])
            else:
                raise CallError(f'Target {target["name"]} is in use.')
        for target_to_extent in await self.middleware.call('iscsi.targetextent.query', [['target', '=', id]]):
            await self.middleware.call('iscsi.targetextent.delete', target_to_extent['id'], force)

        await self.middleware.call(
            'datastore.delete', 'services.iscsitargetgroups', [['iscsi_target', '=', id]]
        )
        rv = await self.middleware.call('datastore.delete', self._config.datastore, id)

        if await self.middleware.call('service.started', 'iscsitarget'):
            # We explicitly need to do this unfortunately as scst does not accept these changes with a reload
            # So this is the best way to do this without going through a restart of the service
            g_config = await self.middleware.call('iscsi.global.config')
            cp = await run([
                'scstadmin', '-force', '-noprompt', '-rem_target',
                f'{g_config["basename"]}:{target["name"]}', '-driver', 'iscsi'
            ], check=False)
            if cp.returncode:
                self.middleware.logger.error('Failed to remove %r target: %s', target['name'], cp.stderr.decode())

        await self._service_change('iscsitarget', 'reload')
        return rv

    @private
    async def active_sessions_for_targets(self, target_id_list):
        targets = await self.middleware.call(
            'iscsi.target.query', [['id', 'in', target_id_list]],
            {'force_sql_filters': True},
        )
        check_targets = []
        global_basename = (await self.middleware.call('iscsi.global.config'))['basename']
        for target in targets:
            name = target['name']
            if not name.startswith(('iqn.', 'naa.', 'eui.')):
                name = f'{global_basename}:{name}'
            check_targets.append(name)

        return [
            s['target'] for s in await self.middleware.call(
                'iscsi.global.sessions', [['target', 'in', check_targets]]
            )
        ]

    @private
    async def compress(self, data):
        data['mode'] = data['mode'].lower()
        for group in data['groups']:
            group['authmethod'] = AUTHMETHOD_LEGACY_MAP.inv.get(group.pop('authmethod'), 'NONE')
        return data


class iSCSITargetToExtentModel(sa.Model):
    __tablename__ = 'services_iscsitargettoextent'
    __table_args__ = (
        sa.Index('services_iscsitargettoextent_iscsi_target_id_757cc851_uniq',
                 'iscsi_target_id', 'iscsi_extent_id',
                 unique=True),
    )

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_extent_id = sa.Column(sa.ForeignKey('services_iscsitargetextent.id'), index=True)
    iscsi_target_id = sa.Column(sa.ForeignKey('services_iscsitarget.id'), index=True)
    iscsi_lunid = sa.Column(sa.Integer())


class iSCSITargetToExtentService(CRUDService):

    class Config:
        namespace = 'iscsi.targetextent'
        datastore = 'services.iscsitargettoextent'
        datastore_prefix = 'iscsi_'
        datastore_extend = 'iscsi.targetextent.extend'
        cli_namespace = 'sharing.iscsi.target.extent'

    @accepts(Dict(
        'iscsi_targetextent_create',
        Int('target', required=True),
        Int('lunid', null=True),
        Int('extent', required=True),
        register=True
    ))
    async def do_create(self, data):
        """
        Create an Associated Target.

        `lunid` will be automatically assigned if it is not provided based on the `target`.
        """
        verrors = ValidationErrors()

        await self.validate(data, 'iscsi_targetextent_create', verrors)

        if verrors:
            raise verrors

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(data['id'])

    def _set_null_false(name):
        def set_null_false(attr):
            attr.null = False
        return {'name': name, 'method': set_null_false}

    @accepts(
        Int('id'),
        Patch(
            'iscsi_targetextent_create',
            'iscsi_targetextent_update',
            ('edit', _set_null_false('lunid')),
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        """
        Update Associated Target of `id`.
        """
        verrors = ValidationErrors()
        old = await self.get_instance(id)

        new = old.copy()
        new.update(data)

        await self.validate(new, 'iscsi_targetextent_update', verrors, old)

        if verrors:
            raise verrors

        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(id)

    @accepts(Int('id'), Bool('force', default=False))
    async def do_delete(self, id, force):
        """
        Delete Associated Target of `id`.
        """
        associated_target = await self.get_instance(id)
        active_sessions = await self.middleware.call(
            'iscsi.target.active_sessions_for_targets', [associated_target['target']]
        )
        if active_sessions:
            if force:
                self.middleware.logger.warning('Associated target %s is in use.', active_sessions[0])
            else:
                raise CallError(f'Associated target {active_sessions[0]} is in use.')

        result = await self.middleware.call(
            'datastore.delete', self._config.datastore, id
        )

        await self._service_change('iscsitarget', 'reload')

        return result

    @private
    async def extend(self, data):
        data['target'] = data['target']['id']
        data['extent'] = data['extent']['id']

        return data

    @private
    async def validate(self, data, schema_name, verrors, old=None):
        if old is None:
            old = {}

        old_lunid = old.get('lunid')
        target = data['target']
        old_target = old.get('target')
        extent = data['extent']
        if data.get('lunid') is None:
            lunids = [
                o['lunid'] for o in await self.query(
                    [('target', '=', target)], {'order_by': ['lunid'], 'force_sql_filters': True}
                )
            ]
            if not lunids:
                lunid = 0
            else:
                diff = sorted(set(range(0, lunids[-1] + 1)).difference(lunids))
                lunid = diff[0] if diff else max(lunids) + 1

            data['lunid'] = lunid
        else:
            lunid = data['lunid']

        # For Linux we have
        # http://github.com/bvanassche/scst/blob/d483590da4de7d32c8371e0712fc186f3d8c509c/scst/include/scst_const.h#L69
        lun_map_size = 16383

        if lunid < 0 or lunid > lun_map_size - 1:
            verrors.add(
                f'{schema_name}.lunid',
                f'LUN ID must be a positive integer and lower than {lun_map_size - 1}'
            )

        if old_lunid != lunid and await self.query([
            ('lunid', '=', lunid), ('target', '=', target)
        ], {'force_sql_filters': True}):
            verrors.add(
                f'{schema_name}.lunid',
                'LUN ID is already being used for this target.'
            )

        if old_target != target and await self.query([
            ('target', '=', target), ('extent', '=', extent)
        ], {'force_sql_filters': True}):
            verrors.add(
                f'{schema_name}.target',
                'Extent is already in this target.'
            )


class ISCSIFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'iscsi'
    title = 'iSCSI Extent'
    service = 'iscsitarget'
    service_class = iSCSITargetExtentService

    async def get_query_filters(self, enabled, options=None):
        return [['type', '=', 'DISK']] + (await super().get_query_filters(enabled, options))

    async def is_child_of_path(self, resource, path):
        dataset_name = os.path.relpath(path, '/mnt')
        full_zvol_path = zvol_name_to_path(dataset_name)
        return is_child(resource[self.path_field], os.path.relpath(full_zvol_path, '/dev'))

    async def delete(self, attachments):
        orphan_targets_ids = set()
        for attachment in attachments:
            for te in await self.middleware.call('iscsi.targetextent.query', [['extent', '=', attachment['id']]]):
                orphan_targets_ids.add(te['target'])
                await self.middleware.call('datastore.delete', 'services.iscsitargettoextent', te['id'])

            await self.middleware.call('datastore.delete', 'services.iscsitargetextent', attachment['id'])
            await self.remove_alert(attachment)

        for te in await self.middleware.call('iscsi.targetextent.query', [['target', 'in', orphan_targets_ids]]):
            orphan_targets_ids.discard(te['target'])
        for target_id in orphan_targets_ids:
            await self.middleware.call('iscsi.target.delete', target_id, True)

        await self._service_change('iscsitarget', 'reload')

    async def restart_reload_services(self, attachments):
        await self._service_change('iscsitarget', 'reload')

    async def stop(self, attachments):
        await self.restart_reload_services(attachments)


async def setup(middleware):
    await middleware.call(
        'interface.register_listen_delegate',
        ISCSIPortalListenDelegate(middleware),
    )
    await middleware.call('pool.dataset.register_attachment_delegate', ISCSIFSAttachmentDelegate(middleware))
