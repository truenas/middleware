from middlewared.schema import accepts, Dict, Str
from middlewared.service import job, Service

import consul
import re
import sys

class ConsulService(Service):

    def set_kv(self, key, value):
        c = consul.Consul()
        return c.kv.put(key, value)

    def get_kv(self, key):
        c = consul.Consul()
        index = None
        index, data = c.kv.get(key, index=index)
        if data is not None:
            return data['Value'].decode("utf-8")
        else:
            return ""

