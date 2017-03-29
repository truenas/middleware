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
        return c.kv.put(str(key), str(value))

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

    @accepts(Str('key'))
    def delete_kv(self, key):
        """
        Delete a `key` in Consul KV.
        """
        c = consul.Consul()
        return c.kv.delete(str(key))
