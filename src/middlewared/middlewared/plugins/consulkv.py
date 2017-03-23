from middlewared.schema import accepts, Any, Str
from middlewared.service import Service

import consul


class ConsulService(Service):

    @accepts(Str('key'), Any('value'))
    def set_kv(self, key, value):
        """
        Sets `key` with `value` in Consul KV.
        """
        c = consul.Consul()
        return c.kv.put(key, value)

    @accepts(Str('key'))
    def get_kv(self, key):
        """
        Gets value of `key` in Consul KV.
        """
        c = consul.Consul()
        index = None
        index, data = c.kv.get(key, index=index)
        if data is not None:
            return data['Value'].decode("utf-8")
        else:
            return ""
