import asyncio
import errno
import os
import pathlib
import re
import subprocess

import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, List, Patch, Str
from middlewared.service import CallError, CRUDService, private, ValidationErrors
from middlewared.utils import UnexpectedFailure, run
from collections import defaultdict

from .utils import AUTHMETHOD_LEGACY_MAP

RE_TARGET_NAME = re.compile(r'^[-a-z0-9\.:]+$')


class iSCSITargetModel(sa.Model):
    __tablename__ = 'services_iscsitarget'

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_target_name = sa.Column(sa.String(120), unique=True)
    iscsi_target_alias = sa.Column(sa.String(120), nullable=True, unique=True)
    iscsi_target_mode = sa.Column(sa.String(20), default='iscsi')
    iscsi_target_auth_networks = sa.Column(sa.JSON(list))


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
    iscsi_target_initiatorgroup_id = sa.Column(
        sa.ForeignKey('services_iscsitargetauthorizedinitiator.id', ondelete='SET NULL'), index=True, nullable=True
    )
    iscsi_target_authtype = sa.Column(sa.String(120), default='None')
    iscsi_target_authgroup = sa.Column(sa.Integer(), nullable=True)
    iscsi_target_initialdigest = sa.Column(sa.String(120), default='Auto')


class iSCSITargetService(CRUDService):

    class Config:
        namespace = 'iscsi.target'
        datastore = 'services.iscsitarget'
        datastore_prefix = 'iscsi_target_'
        datastore_extend = 'iscsi.target.extend'
        cli_namespace = 'sharing.iscsi.target'
        role_prefix = 'SHARING_ISCSI_TARGET'

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
        List('auth_networks', items=[IPAddr('ip', network=True)]),
        register=True
    ))
    async def do_create(self, data):
        """
        Create an iSCSI Target.

        `groups` is a list of group dictionaries which provide information related to using a `portal`, `initiator`,
        `authmethod` and `auth` with this target. `auth` represents a valid iSCSI Authorized Access and defaults to
        null.

        `auth_networks` is a list of IP/CIDR addresses which are allowed to use this initiator. If all networks are
        to be allowed, this field should be left empty.
        """
        verrors = ValidationErrors()
        await self.__validate(verrors, data, 'iscsi_target_create')
        verrors.check()

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

        # First process the local (MASTER) config
        await self._service_change('iscsitarget', 'reload', options={'ha_propagate': False})

        # Then process the remote (BACKUP) config if we are HA and ALUA is enabled.
        if await self.middleware.call("iscsi.global.alua_enabled") and await self.middleware.call('failover.remote_connected'):
            await self.middleware.call('failover.call_remote', 'service.reload', ['iscsitarget'])

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
        if name_error := await self.validate_name(data['name'], old['id'] if old is not None else None):
            verrors.add(f'{schema_name}.name', name_error)

        if data.get('alias') is not None:
            if '"' in data['alias']:
                verrors.add(f'{schema_name}.alias', 'Double quotes are not allowed')
            elif data['alias'] == 'target':
                verrors.add(f'{schema_name}.alias', 'target is a reserved word')
            else:
                filters = [('alias', '=', data['alias'])]
                if old:
                    filters.append(('id', '!=', old['id']))
                aliases = await self.middleware.call(
                    f'{self._config.namespace}.query', filters, {'force_sql_filters': True}
                )
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
                verrors.add(
                    f'{schema_name}.groups.{i}.portal',
                    f'Portal {group["portal"]} cannot be duplicated on a target'
                )
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
                verrors.add(
                    f'{schema_name}.groups.{i}.auth',
                    'Authentication group is required for CHAP and CHAP Mutual'
                )
            elif group['auth'] and group['authmethod'] == 'CHAP_MUTUAL':
                auth = await self.middleware.call('iscsi.auth.query', [('tag', '=', group['auth'])])
                if not auth:
                    verrors.add(f'{schema_name}.groups.{i}.auth', 'Authentication group not found', errno.ENOENT)
                else:
                    if not auth[0]['peeruser']:
                        verrors.add(
                            f'{schema_name}.groups.{i}.auth',
                            f'Authentication group {group["auth"]} does not support CHAP Mutual'
                        )

    @accepts(Str('name'),
             Int('existing_id', null=True, default=None),
             roles=['SHARING_ISCSI_TARGET_WRITE'])
    async def validate_name(self, name, existing_id):
        """
        Returns validation error for iSCSI target name
        :param name: name to be validated
        :param existing_id: id of an existing iSCSI target that will receive this name (or `None` if a new target
                            is being created)
        :return: error message (or `None` if there is no error)
        """
        if not RE_TARGET_NAME.search(name):
            return 'Only lowercase alphanumeric characters plus dot (.), dash (-), and colon (:) are allowed.'
        else:
            filters = [('name', '=', name)]
            if existing_id is not None:
                filters.append(('id', '!=', existing_id))
            names = await self.middleware.call('iscsi.target.query', filters, {'force_sql_filters': True})
            if names:
                return 'Target with this name already exists'

    @accepts(
        Int('id'),
        Patch(
            'iscsi_target_create',
            'iscsi_target_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id_, data):
        """
        Update iSCSI Target of `id`.
        """
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.__validate(verrors, new, 'iscsi_target_create', old=old)
        verrors.check()

        await self.compress(new)
        groups = new.pop('groups')

        oldgroups = old.copy()
        await self.compress(oldgroups)
        oldgroups = oldgroups['groups']

        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.__save_groups(id_, groups, oldgroups)

        # First process the local (MASTER) config
        await self._service_change('iscsitarget', 'reload', options={'ha_propagate': False})

        # Then process the BACKUP config if we are HA and ALUA is enabled.
        if await self.middleware.call("iscsi.global.alua_enabled") and await self.middleware.call('failover.remote_connected'):
            await self.middleware.call('failover.call_remote', 'service.reload', ['iscsitarget'])

        return await self.get_instance(id_)

    @accepts(Int('id'), Bool('force', default=False))
    async def do_delete(self, id_, force):
        """
        Delete iSCSI Target of `id`.

        Deleting an iSCSI Target makes sure we delete all Associated Targets which use `id` iSCSI Target.
        """
        target = await self.get_instance(id_)
        if await self.active_sessions_for_targets([target['id']]):
            if force:
                self.middleware.logger.warning('Target %s is in use.', target['name'])
            else:
                raise CallError(f'Target {target["name"]} is in use.')
        for target_to_extent in await self.middleware.call('iscsi.targetextent.query', [['target', '=', id_]]):
            await self.middleware.call('iscsi.targetextent.delete', target_to_extent['id'], force)

        await self.middleware.call(
            'datastore.delete', 'services.iscsitargetgroups', [['iscsi_target', '=', id_]]
        )
        rv = await self.middleware.call('datastore.delete', self._config.datastore, id_)

        # If HA and ALUA handle BACKUP first
        if await self.middleware.call("iscsi.global.alua_enabled") and await self.middleware.call('failover.remote_connected'):
            await self.middleware.call('failover.call_remote', 'iscsi.target.remove_target', [target["name"]])
            await self.middleware.call('failover.call_remote', 'service.reload', ['iscsitarget'])
            await self.middleware.call('failover.call_remote', 'iscsi.target.logout_ha_target', [target["name"]])

        await self.middleware.call('iscsi.target.remove_target', target["name"])
        await self._service_change('iscsitarget', 'reload', options={'ha_propagate': False})

        return rv

    @private
    @accepts(Str('name'))
    async def remove_target(self, name):
        # We explicitly need to do this unfortunately as scst does not accept these changes with a reload
        # So this is the best way to do this without going through a restart of the service
        if await self.middleware.call('service.started', 'iscsitarget'):
            g_config = await self.middleware.call('iscsi.global.config')
            cp = await run([
                'scstadmin', '-force', '-noprompt', '-rem_target',
                f'{g_config["basename"]}:{name}', '-driver', 'iscsi'
            ], check=False)
            if cp.returncode:
                self.middleware.logger.error('Failed to remove %r target: %s', name, cp.stderr.decode())

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
        # If we specified the alias as the empty string, store it as NULL instead to prevent clash
        # on UNIQUE in the database.
        if data.get("alias", None) == "":
            data['alias'] = None
        return data

    @private
    async def discover(self, ip):
        cmd = ['iscsiadm', '-m', 'discovery', '-t', 'st', '-p', ip]
        err = f'DISCOVER: {ip!r}'
        try:
            cp = await run(cmd, stderr=subprocess.STDOUT, encoding='utf-8')
        except Exception as e:
            err += f' ERROR: {str(e)}'
            raise UnexpectedFailure(err)
        else:
            if cp.returncode != 0:
                err += f' ERROR: {cp.stdout}'
                raise OSError(cp.returncode, os.strerror(cp.returncode), err)

    @private
    async def login_iqn(self, ip, iqn, no_wait=False):
        cmd = ['iscsiadm', '-m', 'node', '-p', ip, '-T', iqn, '--login']
        if no_wait:
            cmd.append('--no_wait')
        err = f'LOGIN: {ip!r} {iqn!r}'
        try:
            cp = await run(cmd, stderr=subprocess.STDOUT, encoding='utf-8')
        except Exception as e:
            err += f' ERROR: {str(e)}'
            raise UnexpectedFailure(err)
        else:
            if cp.returncode != 0:
                err += f' ERROR: {cp.stdout}'
                raise OSError(cp.returncode, os.strerror(cp.returncode), err)

    @private
    async def logout_iqn(self, ip, iqn, no_wait=False):
        cmd = ['iscsiadm', '-m', 'node', '-p', ip, '-T', iqn, '--logout']
        if no_wait:
            cmd.append('--no_wait')
        err = f'LOGOUT: {ip!r} {iqn!r}'
        try:
            cp = await run(cmd, stderr=subprocess.STDOUT, encoding='utf-8')
        except Exception as e:
            err += f' ERROR: {str(e)}'
            raise UnexpectedFailure(err)
        else:
            if cp.returncode != 0:
                err += f' ERROR: {cp.stdout}'
                raise OSError(cp.returncode, os.strerror(cp.returncode), err)

    @private
    def logged_in_iqns(self):
        """
        :return: dict keyed by iqn, with list of the unsurfaced disk names as the value
        """
        results = defaultdict(list)
        p = pathlib.Path('/sys/devices/platform')
        for targetname in p.glob('host*/session*/iscsi_session/session*/targetname'):
            iqn = targetname.read_text().strip()
            for disk in targetname.parent.glob('device/target*/*/scsi_disk'):
                results[iqn].append(disk.parent.name)
        return results

    @private
    def set_genhd_hidden_ips(self, ips):
        """
        Set the kernel parameter /sys/module/iscsi_tcp/parameters/genhd_hidden_ips to the
        specified string, if not already set to it.
        """
        p = pathlib.Path('/sys/module/iscsi_tcp/parameters/genhd_hidden_ips')
        if not p.exists():
            try:
                subprocess.run(["modprobe", "iscsi_tcp"])
            except subprocess.CalledProcessError as e:
                self.logger.error('Failed to load iscsi_tcp kernel module. Error %r', e)
        if p.read_text().rstrip() != ips:
            p.write_text(ips)

    @private
    async def login_ha_targets(self, no_wait=False, raise_error=False):
        """
        When called on a HA BACKUP node will attempt to login to all internal HA targets,
        used in ALUA.

        :return: dict keyed by target name, with list of the unsurfaced disk names or None as the value
        """
        targets = await self.middleware.call('iscsi.target.query')
        global_basename = (await self.middleware.call('iscsi.global.config'))['basename']

        iqns = {}
        for target in targets:
            name = target['name']
            iqns[name] = f'{global_basename}:HA:{name}'

        # Check what's already logged in
        existing = await self.middleware.call('iscsi.target.logged_in_iqns')

        # Generate the set of things we want to login
        todo = set()
        for iqn in iqns.values():
            if iqn not in existing:
                todo.add(iqn)

        if todo:
            remote_ip = await self.middleware.call('failover.remote_ip')

            # Ensure we have configured our kernel so that when we login to the
            # peer controller's iSCSI targets no disk surfaces.
            await self.middleware.call('iscsi.target.set_genhd_hidden_ips', remote_ip)

            # Now we need to do an iscsiadm discovery
            await self.discover(remote_ip)

            # Then login the targets (in parallel)
            exceptions = await asyncio.gather(*[self.login_iqn(remote_ip, iqn, no_wait) for iqn in todo], return_exceptions=True)
            failures = []
            for iqn, exc in zip(todo, exceptions):
                if isinstance(exc, Exception):
                    failures.append(str(exc))
                else:
                    self.logger.info('Successfully logged into %r', iqn)

                if failures:
                    err = f'Failure logging in to targets: {", ".join(failures)}'
                    if raise_error:
                        raise CallError(err)
                    else:
                        self.logger.error(err)

            # Regen existing as it should have now changed
            existing = await self.middleware.call('iscsi.target.logged_in_iqns')

        # Now calculate the result to hand back.
        result = {}
        for name, iqn in iqns.items():
            result[name] = existing.get(iqn, None)

        return result

    @private
    async def logout_ha_target(self, name, no_wait=False):
        global_basename = (await self.middleware.call('iscsi.global.config'))['basename']
        iqn = f'{global_basename}:HA:{name}'
        existing = await self.middleware.call('iscsi.target.logged_in_iqns')
        if iqn in existing:
            remote_ip = await self.middleware.call('failover.remote_ip')
            await self.middleware.call('iscsi.target.logout_iqn', remote_ip, iqn, no_wait)

    @private
    async def logout_ha_targets(self, no_wait=False, raise_error=False):
        """
        When called on a HA BACKUP node will attempt to login to all internal HA targets,
        used in ALUA.
        """
        targets = await self.middleware.call('iscsi.target.query')
        global_basename = (await self.middleware.call('iscsi.global.config'))['basename']

        iqns = {}
        for target in targets:
            name = target['name']
            iqns[name] = f'{global_basename}:HA:{name}'

        # Check what's already logged in
        existing = await self.middleware.call('iscsi.target.logged_in_iqns')

        # Generate the set of things we want to logout (don't assume every IQN, just the HA ones)
        todo = set()
        for iqn in iqns.values():
            if iqn in existing:
                todo.add(iqn)

        if todo:
            remote_ip = await self.middleware.call('failover.remote_ip')

            # Logout the targets (in parallel)
            exceptions = await asyncio.gather(*[self.logout_iqn(remote_ip, iqn, no_wait) for iqn in todo], return_exceptions=True)
            failures = []
            for iqn, exc in zip(todo, exceptions):
                if isinstance(exc, Exception):
                    failures.append(str(exc))
                else:
                    self.logger.info('Successfully logged out from %r', iqn)

                if failures:
                    err = f'Failure logging out from targets: {", ".join(failures)}'
                    if raise_error:
                        raise CallError(err)
                    else:
                        self.logger.error(err)

    @private
    def clustered_extents(self):
        extents = []
        basepath = pathlib.Path('/sys/kernel/scst_tgt/handlers')
        for p in basepath.glob('*/*/cluster_mode'):
            with p.open() as f:
                if f.readline().strip() == '1':
                    extents.append(p.parent.name)
        return extents

    @private
    async def cluster_mode_targets(self):
        """
        Returns a list of target names that are currently in cluster_mode on this controller.
        """
        targets = await self.middleware.call('iscsi.target.query')
        extents = {extent['id']: extent for extent in await self.middleware.call('iscsi.extent.query', [['enabled', '=', True]])}
        assoc = await self.middleware.call('iscsi.targetextent.query')

        # Generate a dict, keyed by target ID whose value is a set of associated extent names
        target_extents = defaultdict(set)
        for a_tgt in filter(
            lambda a: a['extent'] in extents and not extents[a['extent']]['locked'],
            assoc
        ):
            target_extents[a_tgt['target']].add(extents[a_tgt['extent']]['name'])

        # Check sysfs to see what extents are in cluster mode
        cl_extents = set(await self.middleware.call('iscsi.target.clustered_extents'))

        # Now iterate over all the targets and return a list of those whose extents are all
        # in cluster mode.
        result = []
        for target in targets:
            if target_extents[target['id']].issubset(cl_extents):
                result.append(target['name'])

        return result

    @private
    async def cluster_mode_targets_luns(self):
        """
        Returns a tuple containing:
        - list of target names that are currently in cluster_mode on this controller.
        - dict keyed by target name, where the value is a list of luns that are currently in cluster_mode on this controller.
        """
        targets = await self.middleware.call('iscsi.target.query')
        extents = {extent['id']: extent for extent in await self.middleware.call('iscsi.extent.query', [['enabled', '=', True]])}
        assoc = await self.middleware.call('iscsi.targetextent.query')

        # Generate a dict, keyed by target ID whose value is a set of associated extent names
        target_extents = defaultdict(set)
        # Also Generate a dict, keyed by target ID whose value is a set of (lunID, extent name) tuples
        target_luns = defaultdict(set)
        for a_tgt in filter(
            lambda a: a['extent'] in extents and not extents[a['extent']]['locked'],
            assoc
        ):
            target_id = a_tgt['target']
            extent_name = extents[a_tgt['extent']]['name']
            target_extents[target_id].add(extent_name)
            target_luns[target_id].add((a_tgt['lunid'], extent_name))

        # Check sysfs to see what extents are in cluster mode
        cl_extents = set(await self.middleware.call('iscsi.target.clustered_extents'))

        cluster_mode_targets = []
        cluster_mode_luns = defaultdict(list)

        for target in targets:
            # Find targets whose extents are all in cluster mode
            if target_extents[target['id']].issubset(cl_extents):
                cluster_mode_targets.append(target['name'])

            for (lunid, extent_name) in target_luns.get(target['id'], {}):
                if extent_name in cl_extents:
                    cluster_mode_luns[target['name']].append(lunid)

        return (cluster_mode_targets, cluster_mode_luns)

    @private
    async def active_targets(self):
        """
        Returns the names of all targets whose extents are neither disabled nor locked.
        """
        bad_extents = [extent['id'] for extent in await self.middleware.call('iscsi.extent.query',
                                                                             [['OR',
                                                                               [['enabled', '=', False],
                                                                                ['locked', '=', True]]]])]
        targets = {t['id']: t['name'] for t in await self.middleware.call('iscsi.target.query', [], {'select': ['id', 'name']})}
        assoc = {a_tgt['extent']: a_tgt['target'] for a_tgt in await self.middleware.call('iscsi.targetextent.query')}
        for bad_extent in bad_extents:
            del targets[assoc[bad_extent]]
        return list(targets.values())
