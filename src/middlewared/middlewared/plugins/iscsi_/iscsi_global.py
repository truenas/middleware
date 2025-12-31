import asyncio
import ipaddress
import re
import socket

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (ISCSIGlobalAluaEnabledArgs, ISCSIGlobalAluaEnabledResult, ISCSIGlobalEntry,
                                     ISCSIGlobalIserEnabledArgs, ISCSIGlobalIserEnabledResult, ISCSIGlobalUpdateArgs,
                                     ISCSIGlobalUpdateResult)
from middlewared.async_validators import validate_port
from middlewared.plugins.rdma.constants import RDMAprotocols
from middlewared.service import SystemServiceService, ValidationErrors, private
from middlewared.utils import run


RE_IP_PORT = re.compile(r'^(.+?)(:[0-9]+)?$')
DEFAULT_DIRECT_CONFIG = True


class ISCSIGlobalModel(sa.Model):
    __tablename__ = 'services_iscsitargetglobalconfiguration'

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_basename = sa.Column(sa.String(120))
    iscsi_isns_servers = sa.Column(sa.Text())
    iscsi_pool_avail_threshold = sa.Column(sa.Integer(), nullable=True)
    iscsi_alua = sa.Column(sa.Boolean(), default=False)
    iscsi_listen_port = sa.Column(sa.Integer(), nullable=False, default=3260)
    iscsi_iser = sa.Column(sa.Boolean(), default=False)
    iscsi_direct_config = sa.Column(sa.Boolean(), nullable=True)


class ISCSIGlobalService(SystemServiceService):

    class Config:
        datastore = 'services.iscsitargetglobalconfiguration'
        datastore_extend = 'iscsi.global.config_extend'
        datastore_prefix = 'iscsi_'
        service = 'iscsitarget'
        namespace = 'iscsi.global'
        cli_namespace = 'sharing.iscsi.global'
        role_prefix = 'SHARING_ISCSI_GLOBAL'
        entry = ISCSIGlobalEntry

    @private
    def port_is_listening(self, host, port, timeout=5):
        ret = False

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if timeout:
            s.settimeout(timeout)

        try:
            s.connect((host, port))
            ret = True
        except Exception:
            self.logger.debug("connection to %s failed", host, exc_info=True)
            ret = False
        finally:
            s.close()

        return ret

    @private
    def validate_isns_server(self, server: str, verrors: ValidationErrors):
        """Check whether a valid IP[:port] was supplied.

        :return: `(server, ip, port)` tuple on success or `None` on failure.

        """
        invalid_ip_port_tuple = f'Server "{server}" is not a valid IP(:PORT)? tuple.'

        reg = RE_IP_PORT.search(server)
        if not reg:
            verrors.add('iscsiglobal_update.isns_servers', invalid_ip_port_tuple)
            return None

        ip = reg.group(1)
        if ip and ip[0] == '[' and ip[-1] == ']':
            ip = ip[1:-1]

        # First check that a valid IP was supplied
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            verrors.add('iscsiglobal_update.isns_servers', invalid_ip_port_tuple)
            return None

        # Next check the port number (if supplied)
        parts = server.split(':')
        if len(parts) == 2:
            try:
                port = int(parts[1])
            except ValueError:
                valid = False
            else:
                valid = 1 <= port <= 65535

            if not valid:
                verrors.add('iscsiglobal_update.isns_servers', invalid_ip_port_tuple)
                return None
        else:
            port = 3205

        return (server, ip, port)

    @private
    def config_extend(self, data):
        data['isns_servers'] = data['isns_servers'].split()
        return data

    @api_method(
        ISCSIGlobalUpdateArgs,
        ISCSIGlobalUpdateResult,
        audit='Update iSCSI'
    )
    async def do_update(self, data):
        """
        `alua` is a no-op for FreeNAS.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        servers = data.get('isns_servers') or []
        server_addresses = []
        for server in servers:
            if result := self.validate_isns_server(server, verrors):
                server_addresses.append(result)
        if server_addresses:
            # For the valid addresses, we will check connectivity in parallel
            coroutines = [
                self.middleware.call(
                    'iscsi.global.port_is_listening', ip, port
                ) for (server, ip, port) in server_addresses
            ]
            results = await asyncio.gather(*coroutines)
            for (server, ip, port), result in zip(server_addresses, results):
                if not result:
                    verrors.add('iscsiglobal_update.isns_servers', f'Server "{server}" could not be contacted.')

        verrors.extend(await validate_port(
            self.middleware, 'iscsiglobal_update.listen_port', new['listen_port'], 'iscsi.global'
        ))

        if new['iser'] and old['iser'] != new['iser']:
            available_rdma_protocols = await self.middleware.call('rdma.capable_protocols')
            if RDMAprotocols.ISER.value not in available_rdma_protocols:
                verrors.add(
                    "iscsiglobal_update.iser",
                    "This platform cannot support iSER or is missing an RDMA capable NIC."
                )

        verrors.check()

        new['isns_servers'] = '\n'.join(servers)

        licensed = await self.middleware.call('failover.licensed')
        if licensed and old['alua'] != new['alua']:
            if not new['alua']:
                await self.middleware.call(
                    'failover.call_remote', 'service.control', ['STOP', 'iscsitarget'], {'job': True}
                )
                await self.middleware.call('failover.call_remote', 'iscsi.target.logout_ha_targets')

        await self._update_service(old, new, options={'ha_propagate': False})

        if old['direct_config'] != new['direct_config']:
            await self.middleware.call('etc.generate', 'scst_direct')
            if licensed:
                await self.middleware.call(
                    'failover.call_remote', 'etc.generate', ['scst_direct']
                )

        if licensed and old['alua'] != new['alua']:
            if new['alua']:
                await self.middleware.call(
                    'failover.call_remote', 'service.control', ['START', 'iscsitarget'], {'job': True},
                )
            # Force a scst.conf update
            # When turning off ALUA we want to clean up scst.conf, and when turning it on
            # we want to give any existing target a kick to come up as a dev_disk
            await self.middleware.call(
                'failover.call_remote', 'service.control', ['RELOAD', 'iscsitarget'], {'job': True},
            )

        # If we have just turned off iSNS then work around a short-coming in scstadmin reload
        if old['isns_servers'] != new['isns_servers'] and not servers:
            await self.middleware.call('iscsi.global.stop_active_isns')
            if licensed:
                try:
                    await self.middleware.call('failover.call_remote', 'iscsi.global.stop_active_isns')
                except Exception:
                    self.logger.error('Unhandled exception in stop_active_isns on remote controller', exc_info=True)

        # If we have changed the iSER setting and the service is running then restart it
        if old['iser'] != new['iser']:
            if await self.middleware.call('service.started', 'iscsitarget'):
                await (
                    await self.middleware.call('service.control', 'RESTART', 'iscsitarget', {'ha_propagate': False})
                ).wait(raise_error=True)
                if licensed and new['alua'] and old['alua']:
                    # Only need to restart the remote service if it was already running
                    await self.middleware.call(
                        'failover.call_remote', 'service.control', ['RESTART', 'iscsitarget'], {'job': True},
                    )

        return await self.config()

    @private
    async def stop_active_isns(self):
        """
        Unfortunately a SCST reload does not stop a previously active iSNS config, so
        need to be able to perform an explicit action.
        """
        cp = await run([
            'scstadmin', '-force', '-noprompt', '-set_drv_attr', 'iscsi',
            '-attributes', 'iSNSServer=""'
        ], check=False)
        if cp.returncode:
            self.logger.warning('Failed to stop active iSNS: %s', cp.stderr.decode())

    @api_method(
        ISCSIGlobalAluaEnabledArgs,
        ISCSIGlobalAluaEnabledResult,
        roles=['SHARING_ISCSI_GLOBAL_READ']
    )
    async def alua_enabled(self):
        """
        Returns whether iSCSI ALUA is enabled or not.
        """
        if not await self.middleware.call('system.is_enterprise'):
            return False
        if not await self.middleware.call('failover.licensed'):
            return False

        # If FIBRECHANNEL is licensed then allow ALUA
        # if await self.middleware.call('system.feature_enabled', 'FIBRECHANNEL'):
        #     return True

        return (await self.middleware.call('iscsi.global.config'))['alua']

    @api_method(
        ISCSIGlobalIserEnabledArgs,
        ISCSIGlobalIserEnabledResult,
        roles=['SHARING_ISCSI_GLOBAL_READ']
    )
    async def iser_enabled(self):
        """
        Returns whether iSER is enabled or not.
        """
        if not await self.middleware.call('system.is_enterprise'):
            return False

        return (await self.middleware.call('iscsi.global.config'))['iser']

    @private
    async def direct_config_enabled(self):
        """
        Returns whether SCST should be directly configured (via /sys).

        If False then scstadmin will be used.
        """
        direct_config = (await self.middleware.call('iscsi.global.config'))['direct_config']
        if direct_config is None:
            return DEFAULT_DIRECT_CONFIG
        return direct_config
