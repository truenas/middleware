import collections
import typing

from .utils import normalize_value, safely_retrieve_dimension


def get_interface_stats(netdata_metrics: dict, interval: int, interfaces: typing.List[str]) -> dict:
    data = collections.defaultdict(dict)
    for interface_name in interfaces:
        link_state = bool(safely_retrieve_dimension(netdata_metrics, f'net_operstate.{interface_name}', 'up', 0))
        data[interface_name]['link_state'] = 'LINK_STATE_UP' if link_state else 'LINK_STATE_DOWN'
        data[interface_name]['speed'] = safely_retrieve_dimension(
            netdata_metrics, f'net_speed.{interface_name}', 'speed', 0
        )
        if link_state:
            data[interface_name]['received_bytes'] = normalize_value(
                safely_retrieve_dimension(netdata_metrics, f'net.{interface_name}', 'received', 0),
                multiplier=1000,
            ) / interval
            data[interface_name]['sent_bytes'] = normalize_value(
                safely_retrieve_dimension(netdata_metrics, f'net.{interface_name}', 'sent', 0),
                multiplier=1000,
            ) / interval  # FIXME: Test this out
            data[interface_name].update({
                'received_bytes_rate': data[interface_name]['received_bytes'] / interval,
                'sent_bytes_rate': data[interface_name]['sent_bytes'] / interval,
            })
        else:
            data[interface_name].update({
                'received_bytes': 0,
                'sent_bytes': 0,
                'received_bytes_rate': 0,
                'sent_bytes_rate': 0,
            })

        return data
