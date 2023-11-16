import collections
import typing

from .utils import normalize_value, safely_retrieve_dimension


def get_interface_stats(netdata_metrics: dict, interfaces: typing.List[str]) -> dict:
    data = collections.defaultdict(dict)
    for interface_name in interfaces:
        link_state = bool(safely_retrieve_dimension(netdata_metrics, f'net_operstate.{interface_name}', 'up', 0))
        data[interface_name]['link_state'] = 'LINK_STATE_UP' if link_state else 'LINK_STATE_DOWN'
        data[interface_name]['speed'] = normalize_value(safely_retrieve_dimension(
            netdata_metrics, f'net_speed.{interface_name}', 'speed', 0), divisor=1000
        )
        if link_state:
            # In Bluefin, `received_bytes` and `sent_bytes` represent bytes per interval,
            # while `received_bytes_rate` and `sent_bytes_rate` represent bytes per second.
            # However, Netdata is currently sending data in kilobits per second.
            # After converting the Netdata value to bytes per second,
            # we need to multiply `received_bytes` and `sent_bytes` by the interval
            # to maintain unit consistency with Bluefin.
            # https://github.com/truenas/middleware/blob/30dbedbe170b750775e58e7d9c86cfcd00f52730/src/middlewared/
            # middlewared/plugins/reporting/ifstat.py#L73C17-L73C25
            # We have removed received_bytes/sent_bytes from the data structure because of the unneeded computation
            # involved in getting to that and as netdata is giving us kilobit/s already, we just need to convert
            # it to bytes/s

            data[interface_name].update({
                'received_bytes_rate': normalize_value(
                    safely_retrieve_dimension(netdata_metrics, f'net.{interface_name}', 'received', 0),
                    multiplier=1000, divisor=8
                ),
                'sent_bytes_rate': normalize_value(
                    safely_retrieve_dimension(netdata_metrics, f'net.{interface_name}', 'sent', 0),
                    multiplier=1000, divisor=8
                ),
            })
        else:
            data[interface_name].update({
                'received_bytes': 0,
                'sent_bytes': 0,
                'received_bytes_rate': 0,
                'sent_bytes_rate': 0,
            })

    return data
