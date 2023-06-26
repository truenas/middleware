from middlewared.service import Service


class ReportingMemoryService(Service):

    class Config:
        namespace = 'reporting.memory'
        private = True

    async def info(self, allmetrics=None):
        if allmetrics is None:
            allmetrics = await self.middleware.call('netdata.get_all_metrics')

        zfs_arc_unit = allmetrics['zfs.arc_size']['units']
        arcsize = [allmetrics['zfs.arc_size']['dimensions']['size']['value'], zfs_arc_unit]
        arcmax = [allmetrics['zfs.arc_size']['dimensions']['max']['value'], zfs_arc_unit]
        arcmin = [allmetrics['zfs.arc_size']['dimensions']['min']['value'], zfs_arc_unit]

        zfs_hit_unit = allmetrics['zfs.hits']['units']
        archit = [allmetrics['zfs.hits']['dimensions']['hits']['value'], zfs_hit_unit]
        arcmiss = [allmetrics['zfs.hits']['dimensions']['misses']['value'], zfs_hit_unit]

        # system ram (zfs arc is already accounted for in this metric)
        sys_ram_unit = allmetrics['system.ram']['units']
        system_free = [allmetrics['system.ram']['dimensions']['free']['value'], sys_ram_unit]
        system_used = [allmetrics['system.ram']['dimensions']['used']['value'], sys_ram_unit]
        system_total = [system_free + system_used, sys_ram_unit]

        # swap
        if system_swaps := allmetrics.get('system.swap', {}):
            swap_unit = system_swaps['units']
            swap_free = [system_swaps['dimensions']['free']['value'], swap_unit]
            swap_used = [system_swaps['dimensions']['used']['value'], swap_unit]
            swap_total = [swap_free + swap_used, swap_unit]
        else:
            swap_free, swap_used, swap_total = [0.0, 'MiB'], [0.0, 'MiB'], [0.0, 'MiB']

        # webUI uses this for the memory widget on the dashboard and they are only using
        # (at time of writing) the "arc_size", "free", "used", and "total" keys. However,
        # we have access to FAR more memory info if (and when) we want to use those numbers.
        return {
            'zfs': {
                'arc_size': arcsize,
                'arc_max_size': arcmax,
                'arc_min_size': arcmin,
                'arc_hit_percentage': archit,
                'arc_miss_percentage': arcmiss,
            },
            'system': {
                'free': system_free,
                'used': system_used,
                'total': system_total,
                'swap_free': swap_free,
                'swap_used': swap_used,
                'swap_total': swap_total,
            }
        }
