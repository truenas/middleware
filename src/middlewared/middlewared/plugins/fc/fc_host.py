from collections import defaultdict
from typing import Literal

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (FCHostCreateArgs, FCHostCreateResult, FCHostDeleteArgs, FCHostDeleteResult,
                                     FCHostEntry, FCHostUpdateArgs, FCHostUpdateResult)
from middlewared.plugins.failover_.remote import NETWORK_ERRORS
from middlewared.service import CallError, CRUDService, ValidationErrors, private
from .utils import str_to_naa


class FCHostModel(sa.Model):
    __tablename__ = 'services_fc_host'

    id = sa.Column(sa.Integer(), primary_key=True)
    fc_host_alias = sa.Column(sa.String(32), unique=True)
    fc_host_wwpn = sa.Column(sa.String(20), nullable=True, unique=True)
    fc_host_wwpn_b = sa.Column(sa.String(20), nullable=True, unique=True)
    fc_host_npiv = sa.Column(sa.Integer())


class FCHostService(CRUDService):

    class Config:
        private = True
        namespace = "fc.fc_host"
        datastore = "services.fc_host"
        datastore_prefix = 'fc_host_'
        cli_namespace = "sharing.fc.fc_host"
        entry = FCHostEntry
        role_prefix = 'SHARING_ISCSI_TARGET'

    @api_method(FCHostCreateArgs, FCHostCreateResult, audit='Create FC host', audit_extended=lambda data: data['alias'])
    async def do_create(self, data: dict) -> dict:
        """
        Creates FC host (pairing).

        This will associate an `alias` with a corresponding Fibre Channel WWPN.  For
        HA sytems the alias will be associated with a pair of WWPNs, one per node.

        `alias` is a user-readable name for FC host (pairing).

        `wwpn` is the WWPN in naa format (Controller A if HA)

        `wwpn_b` is the WWPN in naa format (Controller B, only applicable for HA)

        `npiv` is the number of NPIV hosts to create for this FC host.
        """
        await self._validate("fc_host_create", data)

        id_ = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        return await self.get_instance(id_)

    @api_method(FCHostUpdateArgs, FCHostUpdateResult, audit='Update FC host', audit_callback=True)
    async def do_update(self, audit_callback: callable, id_: int, data: dict) -> dict:
        """
        Update FC host `id`.

        `alias` is a user-readable name for FC host port.

        `wwpn` is the WWPN in naa format (Controller A if HA)

        `wwpn_b` is the WWPN in naa format (Controller B, only applicable for HA)

        `npiv` is the number of NPIV hosts to allow for this FC host.
        """
        old = await self.get_instance(id_)
        audit_callback(old['alias'])
        new = old.copy()
        new.update(data)

        await self._validate("fc_host_update", new, id_)

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            id_,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        return await self.get_instance(id_)

    @api_method(FCHostDeleteArgs, FCHostDeleteResult, audit='Delete FC host', audit_callback=True)
    async def do_delete(self, audit_callback: callable, id_: int) -> Literal[True]:
        """
        Delete FC host `id`.
        """
        alias = (await self.get_instance(id_))['alias']
        audit_callback(alias)

        response = await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id_
        )

        return response

    async def _get_remote_fc_host_nport_wwpn_choices(self):
        try:
            return await self.middleware.call('failover.call_remote', 'fc.fc_host_nport_wwpn_choices')
        except CallError as e:
            if e.errno in NETWORK_ERRORS + (CallError.ENOMETHOD,):
                # swallow error, but don't present any choices
                return []
            else:
                raise

    async def _validate(self, schema_name: str, data: dict, id_: int = None):
        verrors = ValidationErrors()

        wwpn = data.get('wwpn')
        wwpn_b = data.get('wwpn_b')

        if await self.middleware.call('failover.licensed'):
            # If failover is licensed then we allow both wwpn and wwpn_b to be set,
            # but restricted to the available wwpns on each node
            for key in ['alias', 'wwpn', 'wwpn_b']:
                if data[key] is not None:
                    await self._ensure_unique(verrors, schema_name, key, data[key], id_)
            if wwpn is not None or wwpn_b is not None:
                node = await self.middleware.call('failover.node')
                match node:
                    case 'A':
                        node_a_choices = await self.middleware.call('fc.fc_host_nport_wwpn_choices')
                        node_b_choices = await self._get_remote_fc_host_nport_wwpn_choices()
                    case 'B':
                        node_a_choices = await self._get_remote_fc_host_nport_wwpn_choices()
                        node_b_choices = await self.middleware.call('fc.fc_host_nport_wwpn_choices')
                    case _:
                        raise CallError('Cannot configure FC until HA is configured')
                if wwpn and wwpn not in node_a_choices:
                    verrors.add(
                        f'{schema_name}.wwpn',
                        f'Invalid wwpn ({wwpn}) supplied, should be one of: {",".join(node_a_choices)}'
                    )
                if wwpn_b and wwpn_b not in node_b_choices:
                    verrors.add(
                        f'{schema_name}.wwpn_b',
                        f'Invalid wwpn ({wwpn_b}) supplied, should be one of: {",".join(node_b_choices)}'
                    )
        else:
            for key in ['alias', 'wwpn']:
                if data[key] is not None:
                    await self._ensure_unique(verrors, schema_name, key, data[key], id_)
            if wwpn_b is not None:
                verrors.add(
                    f'{schema_name}.wwpn_b',
                    'May not specify a wwpn for a failover node if not HA'
                )
            if wwpn is not None:
                choices = await self.middleware.call('fc.fc_host_nport_wwpn_choices')
                if wwpn not in choices:
                    verrors.add(
                        f'{schema_name}.wwpn',
                        f'Invalid wwpn ({wwpn}) supplied, should be one of: {",".join(choices)}'
                    )

        verrors.check()

    async def _next_alias(self):
        """
        Return the next unused fc_host alias e.g. "fc0"
        """
        existing = [host['alias'] for host in await self.middleware.call('fc.fc_host.query', [], {'select': ['alias']})]
        count = 0
        while count < 100:
            name = f'fc{count}'
            if name not in existing:
                return name
            count += 1

    async def _get_remote_fc_hosts(self):
        physical_port_filter = [["physical", "=", True]]
        try:
            return await self.middleware.call('failover.call_remote', 'fc.fc_hosts', [physical_port_filter])
        except CallError as e:
            if e.errno in NETWORK_ERRORS + (CallError.ENOMETHOD,):
                # swallow error, but don't present any choices
                return []
            else:
                raise

    @private
    async def wire(self, overwrite=False):
        """
        Wire up fc_host pairings, using the 'slot' field from fc.fc_hosts
        to determine which pairs go together.

        Need to handle the case where the other controller is currently
        down and is therefore unable to give its current config.
        """
        if not await self.middleware.call('fc.capable'):
            return False
        if await self.middleware.call('failover.licensed'):
            # HA
            if await self.middleware.call('failover.status') != 'MASTER':
                self.logger.error('Cannot wire fc_host if not ACTIVE node')
                return False
            node = await self.middleware.call('failover.node')
            slot_2_fc_host_wwpn = defaultdict(dict)
            physical_port_filter = [["physical", "=", True]]
            match node:
                case 'A':
                    node_a_fc_hosts = await self.middleware.call('fc.fc_hosts', physical_port_filter)
                    node_b_fc_hosts = await self._get_remote_fc_hosts()
                case 'B':
                    node_a_fc_hosts = await self._get_remote_fc_hosts()
                    node_b_fc_hosts = await self.middleware.call('fc.fc_hosts', physical_port_filter)
                case _:
                    raise CallError('Cannot configure FC until HA is configured')
            # Match pairs by slow (includes PCI function)
            for fc_host in node_a_fc_hosts:
                slot_2_fc_host_wwpn[fc_host['slot']]['A'] = str_to_naa(fc_host.get('port_name'))
            for fc_host in node_b_fc_hosts:
                slot_2_fc_host_wwpn[fc_host['slot']]['B'] = str_to_naa(fc_host.get('port_name'))
            # Iterate over each slot and make sure the corresponding fc_host entry is preent
            sorted_slots = sorted(list(slot_2_fc_host_wwpn.keys()))
            result = True
            for slot in sorted_slots:
                wwpn = slot_2_fc_host_wwpn[slot].get('A')
                wwpn_b = slot_2_fc_host_wwpn[slot].get('B')
                if wwpn and wwpn_b:
                    existing = await self.middleware.call('fc.fc_host.query', [
                        ['OR', [['wwpn', '=', wwpn], ['wwpn_b', '=', wwpn_b]]]
                    ])
                elif wwpn:
                    existing = await self.middleware.call('fc.fc_host.query', [['wwpn', '=', wwpn]])
                elif wwpn_b:
                    existing = await self.middleware.call('fc.fc_host.query', [['wwpn', '=', wwpn_b]])
                else:
                    existing = []
                if not existing:
                    # Insert new record
                    new_fc_host = {
                        'alias': await self._next_alias(),
                        'wwpn': wwpn,
                        'wwpn_b': wwpn_b,
                        'npiv': 0
                    }
                    await self.middleware.call('fc.fc_host.create', new_fc_host)
                else:
                    # Maybe update record
                    if len(existing) == 1:
                        existing = existing[0]
                        update_fc_host = {}
                        if existing['wwpn'] != wwpn:
                            if existing['wwpn'] is None or overwrite:
                                update_fc_host['wwpn'] = wwpn
                            else:
                                result = False
                        if existing['wwpn_b'] != wwpn_b:
                            if existing['wwpn_b'] is None or overwrite:
                                update_fc_host['wwpn_b'] = wwpn_b
                            else:
                                result = False
                        if update_fc_host:
                            await self.middleware.call('fc.fc_host.update', existing['id'], update_fc_host)
                    else:
                        # Should not occur
                        self.logger.error('Slot "%r" has %d entries: %r', slot, len(existing), existing)
                        result = False
            return result
        else:
            # Not HA - just wire up all fc_hosts in wwpn
            fc_hosts = sorted(await self.middleware.call('fc.fc_hosts'), key=lambda d: d['slot'])
            for fchost in fc_hosts:
                if naa := str_to_naa(fchost.get('port_name')):
                    existing = await self.middleware.call('fc.fc_host.query', [['wwpn', '=', naa]])
                    if not existing:
                        new_fc_host = {
                            'alias': await self._next_alias(),
                            'wwpn': naa,
                            'npiv': 0
                        }
                        await self.middleware.call('fc.fc_host.create', new_fc_host)
            return True
