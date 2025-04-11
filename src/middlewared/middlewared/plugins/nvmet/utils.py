import ipaddress
import uuid

from .constants import NVMET_NQN_UUID


def uuid_nqn():
    # If we wanted a "nqn.2014-08.org.nvmexpress: we could first
    # try to read from /etc/nvme/hostnqn
    # However, since this will be shared between nodes HA nodes,
    # there is an argument that it should not be the hostnqn of
    # either node.
    return f'{NVMET_NQN_UUID}:{uuid.uuid4()}'


def is_ip(value: str, ip_version: int | None = None):
    try:
        ip_address = ipaddress.ip_address(value)
        if any([ip_version is None,
               (ip_version == 4 and isinstance(ip_address, ipaddress.IPv4Address)),
               (ip_version == 6 and isinstance(ip_address, ipaddress.IPv6Address))]):
            return True
    except ValueError:
        pass
    return False
