from middlewared.schema import accepts, Any, Str
from middlewared.service import Service
from middlewared.utils import Popen
from middlewared.client import ejson as json

import middlewared.logger
import consul.aio
import subprocess
import random
import os
import errno

logger = middlewared.logger.Logger('consul').getLogger()


class ConsulService(Service):

    INFLUXDB_API = ['host', 'username', 'password', 'database', 'series-name', 'enabled']
    SLACK_API = ['cluster-name', 'url', 'channel', 'username', 'icon-url', 'detailed', 'enabled']
    MATTERMOST_API = ['cluster', 'url', 'username', 'password', 'team', 'channel', 'enabled']
    PAGERDUTY_API = ['service-key', 'client-name', 'enabled']
    HIPCHAT_API = ['from', 'cluster-name', 'base-url', 'room-id', 'auth-token', 'enabled']
    OPSGENIE_API = ['cluster-name', 'api-key', 'enabled']
    AWSSNS_API = ['reigion', 'topic-arn', 'enabled']
    VICTOROPS_API = ['api-key', 'routing-key', 'enabled']

    @accepts(Str('key'), Any('value'))
    async def set_kv(self, key, value):
        """
        Sets `key` with `value` in Consul KV.

        Returns:
                    bool: True if it added successful the value or otherwise False.
        """
        c = consul.aio.Consul()
        try:
            return await c.kv.put(str(key), str(value))
        except Exception as err:
            logger.error('===> Consul set_kv error: %s' % (err))
            return False

    @accepts(Str('key'))
    async def get_kv(self, key):
        """
        Gets value of `key` in Consul KV.

        Returns:
                    str: Return the value or an empty string.
        """
        c = consul.aio.Consul()
        index = None
        index, data = await c.kv.get(key, index=index)
        if data is not None:
            return data['Value'].decode("utf-8")
        else:
            return ""

    @accepts(Str('key'))
    async def delete_kv(self, key):
        """
        Delete a `key` in Consul KV.

        Returns:
                    bool: True if it could delete the data or otherwise False.
        """
        c = consul.aio.Consul()
        try:
            return await c.kv.delete(str(key))
        except Exception as err:
            logger.error('===> Consul delete_kv error: %s' % (err))
            return False

    @accepts()
    async def reload(self):
        """
        Reload consul agent.

        Returns:
                    bool: True if it could reload, otherwise False.
        """
        consul_error = await (await Popen(['consul', 'reload'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
        if consul_error == 0:
            logger.info("===> Reload Consul: {0}".format(consul_error))
            return True
        else:
            return False

    @accepts()
    async def create_fake_alert(self):
        seed = random.randrange(100000)
        fake_fd = "/usr/local/etc/consul.d/fake.json"
        fake_alert = {"service": {"name": "fake-" + str(seed), "tags": ["primary"],
                                  "address": "", "port": 65535,
                                  "enableTagOverride": False,
                                  "checks": [{"tcp": "localhost:65535",
                                              "interval": "10s", "timeout": "3s"}]
                                  }
                      }
        with open(fake_fd, 'w') as fd:
            fd.write(json.dumps(fake_alert))

        return await self.reload()

    @accepts()
    def remove_fake_alert(self):
        fake_fd = "/usr/local/etc/consul.d/fake.json"
        try:
            os.remove(fake_fd)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

        return self.reload()

    def _convert_keys(self, data):
        """
        Transforms key values that contains "_" to values with "-"

        Returns:
                    dict: With the values on keys using "-".
        """
        for key in list(data.keys()):
            new_key = key.replace("_", "-")
            if new_key != key:
                data[new_key] = data[key]
                del data[key]

        return data

    def _api_keywords(self, api_list, data):
        """
        Helper to convert the API list into a dict.

        Returns:
                    dict: With the API_LIST.
        """
        new_dict = {k: data.get(k, None) for k in api_list}

        return new_dict

    async def _insert_keys(self, prefix, data, api_keywords):
        """
        Helper to insert keys into consul.

        Note: because 'from' is a reserved word in Python, we can't
        use it directly and instead we use hfrom and convert it later.
        """
        new_dict = self._api_keywords(api_keywords, data)

        for k, v in list(new_dict.items()):
            if k == 'hfrom':
                k = 'from'
            await self.set_kv(prefix + k, v)

    async def _delete_keys(self, prefix, data, api_keywords):
        """
        Helper to delete keys into consul.

        Note: The same applies for 'from' like explained on _insert_keys().
        """
        new_dict = self._api_keywords(api_keywords, data)

        for k in list(new_dict.keys()):
            if k == 'hfrom':
                k = 'from'
            await self.delete_kv(prefix + k)

    async def do_create(self, data):
        """
        Helper to insert keys into consul based on the service API.
        """
        consul_prefix = 'consul-alerts/config/notifiers/'
        cdata = self._convert_keys(data)

        alert_service = data.pop('consulalert-type')
        consul_prefix = consul_prefix + alert_service.lower() + '/'

        if alert_service == 'InfluxDB':
            await self._insert_keys(consul_prefix, cdata, self.INFLUXDB_API)
        elif alert_service == 'Slack':
            await self._insert_keys(consul_prefix, cdata, self.SLACK_API)
        elif alert_service == 'Mattermost':
            await self._insert_keys(consul_prefix, cdata, self.MATTERMOST_API)
        elif alert_service == 'PagerDuty':
            await self._insert_keys(consul_prefix, cdata, self.PAGERDUTY_API)
        elif alert_service == 'HipChat':
            await self._insert_keys(consul_prefix, cdata, self.HIPCHAT_API)
        elif alert_service == 'OpsGenie':
            await self._insert_keys(consul_prefix, cdata, self.OPSGENIE_API)
        elif alert_service == 'AWS-SNS':
            await self._insert_keys(consul_prefix, cdata, self.AWSSNS_API)
        elif alert_service == 'VictorOps':
            await self._insert_keys(consul_prefix, cdata, self.VICTOROPS_API)

    async def do_delete(self, alert_service, data):
        """
        Helper to delete the keys from consul based on the service API.
        """
        consul_prefix = 'consul-alerts/config/notifiers/' + alert_service.lower() + '/'
        cdata = self._convert_keys(data)

        if alert_service == 'InfluxDB':
            await self._delete_keys(consul_prefix, cdata, self.INFLUXDB_API)
        elif alert_service == 'Slack':
            await self._delete_keys(consul_prefix, cdata, self.SLACK_API)
        elif alert_service == 'Mattermost':
            await self._delete_keys(consul_prefix, cdata, self.MATTERMOST_API)
        elif alert_service == 'PagerDuty':
            await self._delete_keys(consul_prefix, cdata, self.PAGERDUTY_API)
        elif alert_service == 'HipChat':
            await self._delete_keys(consul_prefix, cdata, self.HIPCHAT_API)
        elif alert_service == 'OpsGenie':
            await self._delete_keys(consul_prefix, cdata, self.OPSGENIE_API)
        elif alert_service == 'AWS-SNS':
            await self._delete_keys(consul_prefix, cdata, self.AWSSNS_API)
        elif alert_service == 'VictorOps':
            await self._delete_keys(consul_prefix, cdata, self.VICTOROPS_API)
