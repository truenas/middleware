from middlewared.schema import accepts, Any, Str
from middlewared.service import Service

import consul


class ConsulService(Service):

    INFLUXDB_API = ['host', 'username', 'password', 'database', 'series-name', 'enabled']
    SLACK_API = ['cluster-name', 'url', 'channel', 'username', 'icon-url', 'detailed', 'enabled']
    MATTERMOST_API = ['cluster', 'url', 'username', 'password', 'team', 'channel', 'enabled']
    PAGERDUTY_API = ['service-key', 'client-name', 'enabled']
    HIPCHAT_API = ['from', 'cluster-name', 'base-url', 'room-id', 'auth-token', 'enabled'] # from
    OPSGENIE_API = ['cluster-name', 'api-key', 'enabled']
    AWSSNS_API = ['reigion', 'topic-arn', 'enabled']
    VICTOROPS_API = ['api-key', 'routing-key', 'enabled']

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

    def _convert_keys(self, data):
        for key in data.keys():
            new_key = key.replace("_", "-")
            if new_key != key:
                data[new_key] = data[key]
                del data[key]

        return data

    def _api_keywords(self, api_list, data):
        new_dict = {k: data.get(k, None) for k in api_list}

        return new_dict

    def _insert_keys(self, prefix, data, api_keywords):
        new_dict = self._api_keywords(api_keywords, data)

        for k, v in new_dict.items():
            if k == 'hfrom':
                k = 'from'
            self.set_kv(prefix + k, v)

    def _delete_keys(self, prefix, data, api_keywords):
        new_dict = self._api_keywords(api_keywords, data)

        for k in new_dict.keys():
            if k == 'hfrom':
                k = 'from'
            self.delete_kv(prefix + k)

    def do_create(self, data):
        consul_prefix = 'consul-alerts/config/notifiers/'
        cdata = self._convert_keys(data)

        alert_service = data.pop('consulalert-type')
        consul_prefix = consul_prefix + alert_service.lower() + '/'

        if alert_service == 'InfluxDB':
            self._insert_keys(consul_prefix, cdata, self.INFLUXDB_API)
        elif alert_service == 'Slack':
            self._insert_keys(consul_prefix, cdata, self.SLACK_API)
        elif alert_service == 'Mattermost':
            self._insert_keys(consul_prefix, cdata, self.MATTERMOST_API)
        elif alert_service == 'PagerDuty':
            self._insert_keys(consul_prefix, cdata, self.PAGERDUTY_API)
        elif alert_service == 'HipChat':
            self._insert_keys(consul_prefix, cdata, self.HIPCHAT_API)
        elif alert_service == 'OpsGenie':
            self._insert_keys(consul_prefix, cdata, self.OPSGENIE_API)
        elif alert_service == 'AWS-SNS':
            self._insert_keys(consul_prefix, cdata, self.AWSSNS_API)
        elif alert_service == 'VictorOps':
            self._insert_keys(consul_prefix, cdata, self.VICTOROPS_API)

    def do_delete(self, alert_service, data):
        consul_prefix = 'consul-alerts/config/notifiers/' + alert_service.lower() + '/'
        cdata = self._convert_keys(data)

        if alert_service == 'InfluxDB':
            self._delete_keys(consul_prefix, cdata, self.INFLUXDB_API)
        elif alert_service == 'Slack':
            self._delete_keys(consul_prefix, cdata, self.SLACK_API)
        elif alert_service == 'Mattermost':
            self._delete_keys(consul_prefix, cdata, self.MATTERMOST_API)
        elif alert_service == 'PagerDuty':
            self._delete_keys(consul_prefix, cdata, self.PAGERDUTY_API)
        elif alert_service == 'HipChat':
            self._delete_keys(consul_prefix, cdata, self.HIPCHAT_API)
        elif alert_service == 'OpsGenie':
            self._delete_keys(consul_prefix, cdata, self.OPSGENIE_API)
        elif alert_service == 'AWS-SNS':
            self._delete_keys(consul_prefix, cdata, self.AWSSNS_API)
        elif alert_service == 'VictorOps':
            self._delete_keys(consul_prefix, cdata, self.VICTOROPS_API)
