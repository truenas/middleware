import asyncio
import errno
import os
import pathlib
import re
import subprocess
from asyncio import Lock
from collections import defaultdict

from pydantic import IPvAnyNetwork

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.api.current import (iSCSITargetCreateArgs, iSCSITargetCreateResult, iSCSITargetDeleteArgs,
                                     iSCSITargetDeleteResult, iSCSITargetEntry, iSCSITargetUpdateArgs,
                                     iSCSITargetUpdateResult, iSCSITargetValidateNameArgs,
                                     iSCSITargetValidateNameResult)
from middlewared.service import CallError, CRUDService, ValidationErrors, private
from middlewared.utils import UnexpectedFailure, run
from .utils import AUTHMETHOD_LEGACY_MAP, sanitize_extent

RE_TARGET_NAME = re.compile(r'^[-a-z0-9\.:]+$')
MODE_FC_CAPABLE = ['FC', 'BOTH']
ISCSI_RELTGT_LOCK = Lock()


class iSCSITargetModel(sa.Model):
    __tablename__ = 'services_iscsitarget'

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_target_name = sa.Column(sa.String(120), unique=True)
    iscsi_target_alias = sa.Column(sa.String(120), nullable=True, unique=True)
    iscsi_target_mode = sa.Column(sa.String(20), default='iscsi')
    iscsi_target_auth_networks = sa.Column(sa.JSON(list))
    iscsi_target_rel_tgt_id = sa.Column(sa.Integer(), unique=True)
    iscsi_target_iscsi_parameters = sa.Column(sa.JSON(), nullable=True)


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


class IscsiTargetRemoveArgs(BaseModel):
    name: str


class IscsiTargetRemoveResult(BaseModel):
    result: None


class iSCSITargetService(CRUDService):

    class Config:
        namespace = 'iscsi.target'
        datastore = 'services.iscsitarget'
        datastore_prefix = 'iscsi_target_'
        datastore_extend = 'iscsi.target.extend'
        cli_namespace = 'sharing.iscsi.target'
        role_prefix = 'SHARING_ISCSI_TARGET'
        entry = iSCSITargetEntry

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

    @api_method(
        iSCSITargetCreateArgs,
        iSCSITargetCreateResult,
        audit='Create iSCSI target',
        audit_extended=lambda data: data['name']
    )
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

        async with ISCSI_RELTGT_LOCK:
            data['rel_tgt_id'] = await self.middleware.call('iscsi.target.get_rel_tgt_id')
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
            await self.middleware.call(
                'failover.call_remote', 'service.control', ['RELOAD', 'iscsitarget'], {'job': True},
            )
            await self.middleware.call('iscsi.alua.wait_for_alua_settled')

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

        for i, network in enumerate(data['auth_networks']):
            try:
                IPvAnyNetwork(network)
            except Exception:
                verrors.add(
                    f'{schema_name}.auth_networks.{i}',
                    f'Auth network "{network}" is not a valid IPv4 or IPv6 network'
                )

    async def __remove_target_fcport(self, id_):
        for fcport in await self.middleware.call('fcport.query', [['target.id', '=', id_]]):
            await self.middleware.call('fcport.delete', fcport['id'])

    @api_method(
        iSCSITargetValidateNameArgs,
        iSCSITargetValidateNameResult,
        roles=['SHARING_ISCSI_TARGET_WRITE']
    )
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

    @api_method(
        iSCSITargetUpdateArgs,
        iSCSITargetUpdateResult,
        audit='Update iSCSI target',
        audit_callback=True
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update iSCSI Target of `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(old['name'])
        new = old.copy()
        new.update(data)

        # Before we compress the data, work out whether we have
        # just removed FC target mode
        remove_fcport = all([old['mode'] != new['mode'],
                             old['mode'] in MODE_FC_CAPABLE,
                             new['mode'] not in MODE_FC_CAPABLE])

        verrors = ValidationErrors()
        await self.__validate(verrors, new, 'iscsi_target_update', old=old)
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

        if remove_fcport:
            await self.__remove_target_fcport(id_)

        # First process the local (MASTER) config
        await self._service_change('iscsitarget', 'reload', options={'ha_propagate': False})

        # Then process the BACKUP config if we are HA and ALUA is enabled.
        alua_enabled = await self.middleware.call("iscsi.global.alua_enabled")
        run_on_peer = alua_enabled and await self.middleware.call('failover.remote_connected')
        if run_on_peer:
            await self.middleware.call(
                'failover.call_remote', 'service.control', ['RELOAD', 'iscsitarget'], {'job': True},
            )

        # NOTE: Any parameters whose keys are omitted will be removed from the config i.e. we
        # will deliberately revert removed items to the SCST default value
        old_params = set(old.get('iscsi_parameters', {}).keys())
        if old_params:
            new_params = set(new.get('iscsi_parameters', {}).keys())
            reset_params = old_params - new_params
            # Has the value just been set to None
            for param in old_params & new_params:
                if new['iscsi_parameters'][param] is None and old['iscsi_parameters'][param] is not None:
                    reset_params.add(param)
            if reset_params:
                global_basename = (await self.middleware.call('iscsi.global.config'))['basename']
                iqn = f'{global_basename}:{new["name"]}'
                await self.middleware.call('iscsi.scst.reset_target_parameters', iqn, list(reset_params))
                if alua_enabled:
                    ha_iqn = f'{global_basename}:HA:{new["name"]}'
                    await self.middleware.call('iscsi.scst.reset_target_parameters', ha_iqn, list(reset_params))
                if run_on_peer:
                    await self.middleware.call('failover.call_remote', 'iscsi.scst.reset_target_parameters', [iqn, list(reset_params)])

        return await self.get_instance(id_)

    @api_method(
        iSCSITargetDeleteArgs,
        iSCSITargetDeleteResult,
        audit='Delete iSCSI target',
        audit_callback=True
    )
    async def do_delete(self, audit_callback, id_, force, delete_extents):
        """
        Delete iSCSI Target of `id`.

        Deleting an iSCSI Target makes sure we delete all Associated Targets which use `id` iSCSI Target.
        """
        target = await self.get_instance(id_)
        audit_callback(target['name'])

        if await self.active_sessions_for_targets([target['id']]):
            if force:
                self.middleware.logger.warning('Target %s is in use.', target['name'])
            else:
                raise CallError(f'Target {target["name"]} is in use.')
        for target_to_extent in await self.middleware.call('iscsi.targetextent.query', [['target', '=', id_]]):
            await self.middleware.call('iscsi.targetextent.delete', target_to_extent['id'], force)
            if delete_extents:
                await self.middleware.call('iscsi.extent.delete', target_to_extent['extent'], False, force)

        # If the target was being used for FC then we may also need to clear the
        # Fibre Channel port mapping
        if target['mode'] in MODE_FC_CAPABLE:
            await self.__remove_target_fcport(id_)

        await self.middleware.call(
            'datastore.delete', 'services.iscsitargetgroups', [['iscsi_target', '=', id_]]
        )
        rv = await self.middleware.call('datastore.delete', self._config.datastore, id_)

        # If HA and ALUA handle BACKUP first
        if await self.middleware.call("iscsi.global.alua_enabled") and await self.middleware.call('failover.remote_connected'):
            await self.middleware.call('failover.call_remote', 'iscsi.target.remove_target', [target["name"]])
            await self.middleware.call(
                'failover.call_remote', 'service.control', ['RELOAD', 'iscsitarget'], {'job': True},
            )
            await self.middleware.call('failover.call_remote', 'iscsi.target.logout_ha_target', [target["name"]])
            await self.middleware.call('iscsi.alua.wait_for_alua_settled')

        await self.middleware.call('iscsi.target.remove_target', target["name"])
        await self._service_change('iscsitarget', 'reload', options={'ha_propagate': False})

        return rv

    @api_method(
        IscsiTargetRemoveArgs,
        IscsiTargetRemoveResult,
        private=True
    )
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
    async def get_rel_tgt_id(self):
        """ WARNING: this endpoint must be called while holding ISCSI_RELTGT_LOCK """
        existing = {
            target['rel_tgt_id']
            for target in await self.middleware.call(f'{self._config.namespace}.query', [], {'select': ['rel_tgt_id']})
        }

        for i in range(1, 32000):
            if i not in existing:
                return i

        raise ValueError("Unable to deletmine rel_tgt_id")

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
    async def logout_iqn(self, ip, iqn, no_wait=False, timeout=30):
        cmd = ['iscsiadm', '-m', 'node', '-p', ip, '-T', iqn, '--logout']
        if no_wait:
            cmd.append('--no_wait')
        err = f'LOGOUT: {ip!r} {iqn!r}'
        try:
            cp = await run(cmd, stderr=subprocess.STDOUT, encoding='utf-8', timeout=timeout)
        except Exception as e:
            err += f' ERROR: {str(e)}'
            raise UnexpectedFailure(err)
        else:
            if cp.returncode != 0:
                err += f' ERROR: {cp.stdout}'
                raise OSError(cp.returncode, os.strerror(cp.returncode), err)

    @private
    async def rescan_iqn(self, iqn, timeout=30):
        cmd = ['iscsiadm', '-m', 'node', '-T', iqn, '-R']
        await run(cmd, stderr=subprocess.STDOUT, encoding='utf-8', timeout=timeout)

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
    def logged_in_empty_iqns(self):
        """
        :return: list of logged in iqns without any associated unsurfaced disks
        """
        results = []
        p = pathlib.Path('/sys/devices/platform')
        for targetname in p.glob('host*/session*/iscsi_session/session*/targetname'):
            found = False
            iqn = targetname.read_text().strip()
            for _item in targetname.parent.glob('device/target*/*/scsi_disk'):
                found = True
                break
            if not found:
                results.append(iqn)
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
        iqns = await self.middleware.call('iscsi.target.active_ha_iqns')
        global_basename = (await self.middleware.call('iscsi.global.config'))['basename']

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

            # This below one does NOT have the desired impact, despite the output from 'iscsiadm -m node -o show'
            # cmd = ['iscsiadm', '-m', 'node', '-o', 'update', '-n', 'node.session.timeo.replacement_timeout', '-v', '10']
            # await run(cmd, stderr=subprocess.STDOUT, encoding='utf-8')
            # So instead do this.
            await self.middleware.call('iscsi.target.set_ha_targets_sys', f'{global_basename}:HA:', 'recovery_tmo', '10\n')

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
        ha_iqn_prefix_str = await self.middleware.call('iscsi.target.ha_iqn_prefix')

        # Check what's already logged in
        existing = await self.middleware.call('iscsi.target.logged_in_iqns')

        # Generate the set of things we want to logout (don't assume every IQN, just the HA ones)
        todo = set()
        for iqn in existing.keys():
            if iqn.startswith(ha_iqn_prefix_str):
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
    async def logout_empty_ha_targets(self, no_wait=False, raise_error=False):
        """
        When called on a HA BACKUP node will attempt to login to all HA targets,
        used in ALUA which are not currently associated with a LUN.

        This can occur if they target is reporting as BUSY (i.e. suspended) during login.
        """
        iqns = await self.middleware.call('iscsi.target.active_ha_iqns')

        # Check what's already logged in, but has no LUNs
        existing = await self.middleware.call('iscsi.target.logged_in_empty_iqns')

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
        # Extents may have had their names sanitized for SCST.  We want the official
        # unsanitized names as output.
        sys_to_name = {sanitize_extent(ext['name']): ext['name'] for ext in
                       self.middleware.call_sync('iscsi.extent.query', [], {'select': ['name']})}
        extents = []
        basepath = pathlib.Path('/sys/kernel/scst_tgt/handlers')
        for p in basepath.glob('*/*/cluster_mode'):
            with p.open() as f:
                if f.readline().strip() == '1':
                    try:
                        extents.append(sys_to_name[p.parent.name])
                    except KeyError:
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
        # in cluster mode.  Exclude targets with no extents.
        result = []
        for target in targets:
            if target_extents[target['id']] and target_extents[target['id']].issubset(cl_extents):
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
            # Find targets whose extents are all in cluster mode.  Exclude targets with no extents.
            if target_extents[target['id']] and target_extents[target['id']].issubset(cl_extents):
                cluster_mode_targets.append(target['name'])

            for (lunid, extent_name) in target_luns.get(target['id'], {}):
                if extent_name in cl_extents:
                    cluster_mode_luns[target['name']].append(lunid)

        return (cluster_mode_targets, cluster_mode_luns)

    @private
    async def active_targets(self):
        """
        Returns the names of all targets whose extents are neither disabled nor locked,
        and which have at least one extent configured.
        """
        filters = [['OR', [['enabled', '=', False], ['locked', '=', True]]]]
        bad_extents = []
        for extent in await self.middleware.call('iscsi.extent.query', filters):
            bad_extents.append(extent['id'])

        targets = {t['id']: t['name'] for t in await self.middleware.call('iscsi.target.query', [], {'select': ['id', 'name']})}
        assoc = {a_tgt['extent']: a_tgt['target'] for a_tgt in await self.middleware.call('iscsi.targetextent.query')}
        for bad_extent in bad_extents:
            # the disabled / locked extent may not have a target mapping and so we need additional check here before
            # removing it from list of active targets to avoid crashing here
            if bad_extent in assoc:
                targets.pop(assoc[bad_extent], None)

        # Also discount targets that do not have any extents
        targets_with_extents = assoc.values()
        for target_id in list(targets.keys()):
            if target_id not in targets_with_extents:
                del targets[target_id]

        return list(targets.values())

    @private
    async def active_ha_iqns(self):
        """Return a dict keyed by target name with a value of the corresponding HA IQN for all
        targets that are deemed to be active_targets (i.e. no disabled of locked extents, and
        at least one extent configured)."""
        targets = await self.middleware.call('iscsi.target.active_targets')
        global_basename = (await self.middleware.call('iscsi.global.config'))['basename']

        iqns = {}
        for name in targets:
            iqns[name] = f'{global_basename}:HA:{name}'

        return iqns

    @private
    def set_ha_targets_sys(self, iqn_prefix, param, text):
        sys_platform = pathlib.Path('/sys/devices/platform')
        for targetname in sys_platform.glob('host*/session*/iscsi_session/session*/targetname'):
            if targetname.read_text().startswith(iqn_prefix):
                targetname.parent.joinpath(param).write_text(text)

    @private
    async def ha_iqn_prefix(self):
        global_basename = (await self.middleware.call('iscsi.global.config'))['basename']
        return f'{global_basename}:HA:'

    @private
    async def ha_iqn(self, name):
        """Return the IQN of the specified internal target."""
        prefix = await self.middleware.call('iscsi.target.ha_iqn_prefix')
        return f'{prefix}{name}'

    @private
    def iqn_ha_luns(self, iqn):
        """Return a list of (integer) LUNs which are offered by the specified IQN."""
        result = []
        try:
            with os.scandir(f'/sys/kernel/scst_tgt/targets/iscsi/{iqn}/luns') as entries:
                for entry in filter(lambda x: x.name.isnumeric(), entries):
                    result.append(int(entry.name))
        except FileNotFoundError:
            pass
        return result
