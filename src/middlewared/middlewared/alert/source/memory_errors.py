from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, AlertSource


class MemoryErrorsNoInfoAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'Uncorrected Memory Errors Detected'
    text = '%(count)d total uncorrected errors detected for memory controller "%(mc)s".'
    products = ('SCALE_ENTERPRISE',)
    proactive_support = True


class MemoryErrorsInfoAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'Uncorrected Memory Errors Detected'
    text = '%(count)d total uncorrected errors detected for memory controller "%(mc)s" on "%(dimm)s".'
    products = ('SCALE_ENTERPRISE',)
    proactive_support = True


class MemoryErrorsAlertSource(AlertSource):

    async def check(self):
        alerts = []
        for mem_ctrl, info in (await self.middleware.call('hardware.memory.error_info')).items():
            if (val := info['uncorrected_errors_with_no_dimm_info']) is not None and val > 0:
                # this means that there were uncorrected errors where no additional information
                # is available. These errors occur when the system detects an uncorrectable memory
                # error, but specific details about the error are not provided or accessible.
                # Because of this fact, we'll just report the error count without the DIMM information.
                alerts.append(Alert(MemoryErrorsNoInfoAlertClass, {'mc': mem_ctrl, 'count': val}))
            elif (val := info['uncorrected_errors']) is not None and val > 0:
                # this means that there were uncorrected errors where the dimm information was able
                # to be obtained.
                for dimm_key in filter(lambda x: x.startswith(('dimm', 'rank')), info):
                    if (val2 := info[dimm_key]['uncorrected_errors']) is not None and val2 > 0:
                        # the specific dimm
                        alerts.append(Alert(
                            MemoryErrorsInfoAlertClass, {'mc': mem_ctrl, 'count': val2, 'dimm': dimm_key}
                        ))

        return alerts
