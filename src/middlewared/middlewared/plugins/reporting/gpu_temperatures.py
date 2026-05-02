from middlewared.service import Service, private


class ReportingService(Service):

    @private
    async def gpu_temperatures(self):
        netdata_metrics = await self.middleware.call('netdata.get_all_metrics')
        data = {}
        temp_retrieved = False
        for name, gpu_temp in netdata_metrics.get('gputemp.temperatures', {'dimensions': {}})['dimensions'].items():
            data[name] = gpu_temp['value']
            if not temp_retrieved:
                temp_retrieved = bool(gpu_temp['value'])
        return data if temp_retrieved else {}
