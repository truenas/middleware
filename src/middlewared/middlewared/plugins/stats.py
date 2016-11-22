from middlewared.service import Service

import glob
import os


RRD_PATH = '/var/db/collectd/rrd/localhost/'


class StatsService(Service):

    def get_sources(self):
        sources = {}
        if not os.path.exists(RRD_PATH):
            return {}
        for i in glob.glob('{}/*/*.rrd'.format(RRD_PATH)):
            source, metric = i.replace(RRD_PATH, '').split('/', 1)
            if metric.endswith('.rrd'):
                metric = metric[:-4]
            if source not in sources:
                sources[source] = []
            sources[source].append(metric)
        return sources
