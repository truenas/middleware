from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, AlertSource
from middlewared.alert.schedule import CrontabSchedule


class RESTAPIUsageAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Deprecated REST API usage"
    text = (
        "The deprecated REST API was used to authenticate %(count)d times in the last "
        "24 hours from the following IP addresses:<br>%(ip_addresses)s.<br>"
        "The REST API will be removed in version 26.04. To avoid service disruption, "
        "migrate any remaining integrations to the supported JSON-RPC 2.0 over WebSocket API before "
        "upgrading. For migration guidance, see the "
        "<a href=\"https://api.truenas.com/v26.04/jsonrpc.html\" target=\"_blank\">documentation</a>."
    )


class RESTAPIUsageAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)  # every 24 hours
    run_on_backup_node = True

    async def check(self):
        qf = [
            ['event', '=', 'AUTHENTICATION'],
            ['service_data.protocol', '=', 'LEGACY_REST'],
            ['success', '=', True]
        ]

        rest_api_call_count = await self.middleware.call('audit.query', {
            'services': ['MIDDLEWARE'],
            'query-filters': qf,
            'query-options': {'count': True}
        })
        if not rest_api_call_count:
            return None

        rest_api_calls = await self.middleware.call('audit.query', {
            'services': ['MIDDLEWARE'],
            'query-filters': qf,
            'query-options': {
                'select': [
                    'address',
                ],
                'limit': 1000,
            }
        })
        if not rest_api_calls:
            return None

        rest_api_call_ips = ', '.join(sorted({entry['address'] for entry in rest_api_calls}))

        return Alert(
            RESTAPIUsageAlertClass,
            {'count': rest_api_call_count, 'ip_addresses': rest_api_call_ips},
            key=None
        )
