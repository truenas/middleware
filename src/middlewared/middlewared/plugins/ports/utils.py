import ipaddress

from middlewared.common.ports import WILDCARD_IPS


SYSTEM_PORTS: list[tuple[str, int]] = [
    (wildcard, port) for wildcard in WILDCARD_IPS for port in [67, 123, 1700, 3702, 5353, 6000]
]


def get_ip_version(ip: str) -> int:
    return ipaddress.ip_interface(ip).version
