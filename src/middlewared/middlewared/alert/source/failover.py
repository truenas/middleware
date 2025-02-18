# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import errno

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource, UnavailableException
from middlewared.utils import ProductType
from middlewared.service_exception import CallError


class FailoverInterfaceNotFoundAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = 'Failover Internal Interface Not Found'
    text = 'Failover internal interface not found. Contact support.'
    products = (ProductType.ENTERPRISE,)


class TrueNASVersionsMismatchAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = 'TrueNAS Software Versions Must Match Between Storage Controllers'
    text = 'TrueNAS software versions must match between storage controllers.'
    products = (ProductType.ENTERPRISE,)


class FailoverStatusCheckFailedAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = 'Failed to Check Failover Status with the Other Controller'
    text = 'Failed to check failover status with the other controller: %s.'
    products = (ProductType.ENTERPRISE,)


class FailoverFailedAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = 'Failover Failed'
    text = 'Failover failed. Check /var/log/failover.log on both controllers.'
    products = (ProductType.ENTERPRISE,)


class VRRPStatesDoNotAgreeAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = 'Controllers VRRP States Do Not Agree'
    text = 'Controllers VRRP states do not agree: %(error)s.'
    products = (ProductType.ENTERPRISE,)


class FailoverAlertSource(AlertSource):
    products = (ProductType.ENTERPRISE,)
    failover_related = True
    run_on_backup_node = False

    async def check(self):
        if not await self.middleware.call('failover.internal_interfaces'):
            return [Alert(FailoverInterfaceNotFoundAlertClass)]

        try:
            if not await self.middleware.call('failover.call_remote', 'system.ready'):
                raise UnavailableException()

            local_version = await self.middleware.call('system.version')
            remote_version = await self.middleware.call('failover.call_remote', 'system.version')
            if local_version != remote_version:
                return [Alert(TrueNASVersionsMismatchAlertClass)]

            local = await self.middleware.call('failover.vip.get_states')
            remote = await self.middleware.call('failover.call_remote', 'failover.vip.get_states')
            if err := await self.middleware.call('failover.vip.check_states', local, remote):
                return [Alert(VRRPStatesDoNotAgreeAlertClass, {'error': i}) for i in err]
        except CallError as e:
            if e.errno != errno.ECONNREFUSED:
                return [Alert(FailoverStatusCheckFailedAlertClass, [str(e)])]

        if await self.middleware.call('failover.status') in ('ERROR', 'UNKNOWN'):
            return [Alert(FailoverFailedAlertClass)]

        return []
