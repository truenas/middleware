from middlewared.service import private, Service


class ReportingService(Service):

    @private
    async def cpu_temperatures(self):
        netdata_metrics = await self.middleware.call('netdata.get_all_metrics')
        data = {}
        for core, cpu_temp in netdata_metrics.get('cputemp.temperatures', {'dimensions': {}})['dimensions'].items():
            data[core] = cpu_temp['value']
        return data
