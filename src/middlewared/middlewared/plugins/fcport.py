import os
import subprocess
from typing import Literal

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (FCPortCreateArgs, FCPortCreateResult, FCPortDeleteArgs, FCPortDeleteResult,
                                     FCPortEntry, FCPortUpdateArgs, FCPortUpdateResult)
from middlewared.service import CRUDService, ValidationErrors, private
from middlewared.service_exception import MatchNotFound
from .fc.utils import wwpn_to_vport

VPORT_SEP_CHAR = '/'
QLA2XXX_KERNEL_TARGET_MODULE = 'qla2x00tgt'


class FCPortModel(sa.Model):
    __tablename__ = 'services_fibrechanneltotarget'

    id = sa.Column(sa.Integer(), primary_key=True)
    fc_port = sa.Column(sa.String(40))
    fc_target_id = sa.Column(sa.ForeignKey('services_iscsitarget.id'), nullable=True, index=True)


class FCPortService(CRUDService):

    class Config:
        private = True
        namespace = "fcport"
        datastore = "services.fibrechanneltotarget"
        datastore_prefix = 'fc_'
        datastore_extend = 'fcport.extend'
        cli_namespace = "sharing.fc_port"
        entry = FCPortEntry
        role_prefix = 'SHARING_ISCSI_TARGET'

    @api_method(FCPortCreateArgs, FCPortCreateResult, audit='Create FC port mapping', audit_extended=lambda data: data['alias'])
    async def do_create(self, data: dict) -> dict:
        """
        Creates mapping between a FC port and a target.

        `name` is a user-readable name for key.
        """
        await self._validate("fcport_create", data)

        await self.compress(data)

        orig_count = await self.count()

        pk = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self.update_scst(orig_count == 0)

        return await self.get_instance(pk)

    @api_method(FCPortUpdateArgs, FCPortUpdateResult, audit='Update FC port mapping', audit_callback=True)
    async def do_update(self, audit_callback: callable, id_: int, data: dict) -> dict:
        """
        Update FC port mapping `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(old['port'])
        new = old.copy()
        new.update(data)

        await self._validate("fcport_update", new, id_)

        await self.compress(new)

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            id_,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.update_scst()

        return await self.get_instance(id_)

    @api_method(FCPortDeleteArgs, FCPortDeleteResult, audit='Delete FC port mapping', audit_callback=True)
    async def do_delete(self, audit_callback: callable, id_: int) -> Literal[True]:
        """
        Delete FC port mapping `id`.
        """
        alias = (await self.get_instance(id_))['port']
        audit_callback(alias)

        response = await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id_
        )

        await self.update_scst()

        return response

    async def _validate(self, schema_name: str, data: dict, id_: int = None):
        verrors = ValidationErrors()

        # Make sure we don't reuse either port or target_id
        for key in ['port', 'target_id']:
            await self._ensure_unique(verrors, schema_name, key, data[key], id_)

        # Make sure that the port base is a valid fc_host alias
        fc_hosts = {host['alias']: host for host in await self.middleware.call('fc.fc_host.query')}
        port = data.get('port')
        if port:
            if VPORT_SEP_CHAR in port:
                # NPIV - Get the base FC Host
                fc_host_alias, chan = port.rsplit(VPORT_SEP_CHAR, 1)
            else:
                fc_host_alias = port
                chan = None
            if fc_host_alias in fc_hosts:
                # Valid base, may need to check NPIV chan
                if chan is not None:
                    if chan.isdigit():
                        npiv_setting = fc_hosts[fc_host_alias]['npiv']
                        if int(chan) > npiv_setting:
                            verrors.add(
                                f'{schema_name}.port',
                                f'Invalid FC port ({port}) supplied, chan {chan} is greater than NPIV setting {npiv_setting}'
                            )
                        elif int(chan) == 0:
                            verrors.add(
                                f'{schema_name}.port',
                                f'Invalid FC port ({port}) supplied, chan {chan} must be greater than 0 and less than NPIV setting {npiv_setting}'
                            )
                    else:
                        verrors.add(
                            f'{schema_name}.port',
                            f'Invalid FC port ({port}) supplied, digits only after "{VPORT_SEP_CHAR}"'
                        )
            else:
                verrors.add(
                    f'{schema_name}.port',
                    f'Invalid FC port ({port}) supplied, should be one of: {",".join(fc_hosts.keys())}'
                )
        else:
            verrors.add(
                f'{schema_name}.port',
                f'No FC port supplied, should be based on one of: {",".join(fc_hosts.keys())}'
            )

        # Test the target supplied
        target_id = data.get('target_id')
        if target_id is not None:
            try:
                target = await self.middleware.call('iscsi.target.query', [['id', '=', target_id]], {'get': True})
            except MatchNotFound:
                verrors.add(
                    f'{schema_name}.target_id',
                    f'No target exists with the specified id {target_id}'
                )
            else:
                target_mode = target['mode']
                if target_mode not in ['FC', 'BOTH']:
                    target_name = target['name']
                    verrors.add(
                        f'{schema_name}.target_id',
                        f'Specified target "{target_name}" ({target_id}) does not have a "mode" ({target_mode}) that permits FC access'
                    )

        verrors.check()

    @private
    async def compress(self, data):
        for key in ['wwpn', 'wwpn_b']:
            if key in data:
                data.pop(key)
        return data

    @private
    async def extend(self, data):
        data['wwpn'] = None
        data['wwpn_b'] = None
        # We want to retrieve the WWPN associated with the port name
        if VPORT_SEP_CHAR in data['port']:
            # NPIV - Get the base FC Host
            fc_host_alias, chan = data['port'].rsplit(VPORT_SEP_CHAR, 1)
        else:
            fc_host_alias = data['port']
            chan = None
        try:
            fc_host_pair = await self.middleware.call('fc.fc_host.query', [['alias', '=', fc_host_alias]], {'get': True})
        except MatchNotFound:
            pass
        else:
            if chan:
                # NPIV
                data['wwpn'] = wwpn_to_vport(fc_host_pair.get('wwpn'), int(chan))
                data['wwpn_b'] = wwpn_to_vport(fc_host_pair.get('wwpn_b'), int(chan))
            else:
                # Non-NPIV
                data['wwpn'] = fc_host_pair.get('wwpn')
                data['wwpn_b'] = fc_host_pair.get('wwpn_b')
        return data

    @private
    async def count(self):
        return await self.middleware.call(
            "datastore.query",
            self._config.datastore,
            [],
            {'count': True}
        )

    def __load_kernel_module(self):
        # If SCST has already started, but the kernel target module is not already loaded
        if os.path.isdir('/sys/kernel/scst_tgt/targets') and not os.path.isdir('/sys/kernel/scst_tgt/targets/qla2x00t'):
            self.logger.info('Loading kernel module %r', QLA2XXX_KERNEL_TARGET_MODULE)
            try:
                subprocess.run(["modprobe", QLA2XXX_KERNEL_TARGET_MODULE])
            except subprocess.CalledProcessError as e:
                self.logger.error('Failed to load kernel module. Error %r', e)

    @private
    async def load_kernel_module(self):
        """
        Load the Fibre Channel kernel target module.
        """
        await self.middleware.run_in_thread(self.__load_kernel_module)

    @private
    async def update_scst(self, do_module_load=False):
        # First process the local (MASTER) config
        if do_module_load:
            await self.middleware.run_in_thread(self.__load_kernel_module)

        await self._service_change('iscsitarget', 'reload', options={'ha_propagate': False})

        # Then process the BACKUP config if we are HA and ALUA is enabled.
        if await self.middleware.call("iscsi.global.alua_enabled") and await self.middleware.call('failover.remote_connected'):
            if do_module_load:
                await self.middleware.call('failover.call_remote', 'fcport.load_kernel_module')
            await self.middleware.call('failover.call_remote', 'service.reload', ['iscsitarget'])
            await self.middleware.call('iscsi.alua.wait_for_alua_settled')
