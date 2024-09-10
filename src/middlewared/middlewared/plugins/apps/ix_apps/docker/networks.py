from .casing import convert_case_for_dict_or_list
from .utils import get_docker_client


def list_networks() -> list[dict]:
    networks = []
    with get_docker_client() as client:
        for network in client.networks.list(greedy=False):
            attrs = network.attrs | {'short_id': network.short_id}
            attrs['enable_ipv6'] = attrs.pop('EnableIPv6', False)
            networks.append(convert_case_for_dict_or_list(attrs))

    return networks
