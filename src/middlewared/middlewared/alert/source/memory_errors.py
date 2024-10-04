# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, AlertSource
from middlewared.alert.schedule import CrontabSchedule
from middlewared.plugins.system.product import ProductType
from middlewared.utils.size import format_size


class MemoryErrorsAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'Uncorrected Memory Errors Detected'
    text = '%(count)d total uncorrected errors detected for %(loc)s.'
    products = (ProductType.SCALE_ENTERPRISE,)
    proactive_support = True


class MemorySizeMismatchAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'Memory Size Mismatch Detected'
    text = 'Memory size on this controller %(r1)s doesn\'t match other controller %(r2)s'
    products = (ProductType.SCALE_ENTERPRISE,)
    proactive_support = True


class MemoryErrorsAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)  # every 24hrs

    async def check(self):
        alerts = []
        for mem_ctrl, info in (await self.middleware.call('hardware.memory.error_info')).items():
            location = f'memory controller {mem_ctrl}'
            if (val := info['uncorrected_errors_with_no_dimm_info']) is not None and val > 0:
                # this means that there were uncorrected errors where no additional information
                # is available. These errors occur when the system detects an uncorrectable memory
                # error, but specific details about the error are not provided or accessible.
                # Because of this fact, we'll just report the error count without the DIMM information.
                alerts.append(Alert(MemoryErrorsAlertClass, {'count': val, 'loc': location}))
            elif (val := info['uncorrected_errors']) is not None and val > 0:
                # this means that there were uncorrected errors where the dimm information was able
                # to be obtained.
                for dimm_key in filter(lambda x: x.startswith(('dimm', 'rank')), info):
                    if (val2 := info[dimm_key]['uncorrected_errors']) is not None and val2 > 0:
                        # the specific dimm
                        alerts.append(Alert(
                            MemoryErrorsAlertClass, {'count': val2, 'loc': location + f' on dimm {dimm_key}'}
                        ))

        return alerts


class MemorySizeMismatchAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)  # every 24hrs
    run_on_backup_node = False

    async def check(self):
        alerts = []
        if not await self.middleware.call('failover.licensed'):
            return alerts

        r1 = (await self.middleware.call('system.mem_info'))['physmem_size']
        if r1 is None:
            return alerts

        try:
            r2 = await self.middleware.call(
                'failover.call_remote', 'system.mem_info', {'raise_connect_error': False}
            )
            if r2['physmem_size'] is None:
                return alerts
        except Exception:
            return alerts

        if r1 != r2:
            alerts.append(Alert(
                MemorySizeMismatchAlertClass,
                {'r1': format_size(r1), 'r2': format_size(r2)}
            ))

        return alerts
