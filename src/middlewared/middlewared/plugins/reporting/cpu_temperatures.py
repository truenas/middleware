from middlewared.service import private, Service


class ReportingService(Service):

    @private
    async def cpu_temperatures(self):
        netdata_metrics = await self.middleware.call('netdata.get_all_metrics')
        data = {}
        temp_retrieved = False
        for core, cpu_temp in netdata_metrics.get('cputemp.temperatures', {'dimensions': {}})['dimensions'].items():
            data[core] = cpu_temp['value']
            if not temp_retrieved:
                temp_retrieved = bool(cpu_temp['value'])
        return data if temp_retrieved else {}
