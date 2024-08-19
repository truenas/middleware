from dataclasses import dataclass
from socket import inet_ntoa, inet_ntop, AF_INET6
from struct import pack

__all__ = ('read_proc_net',)


@dataclass(slots=True, frozen=True)
class InetInfoEntry:
    local_ip: str
    local_port: int
    remote_ip: str
    remote_port: int
    protocol: str


def parse_address(hex_address, ipversion):
    ip_hex, port_hex = hex_address.split(':')
    if ipversion == '4':
        ip = inet_ntoa(pack("<L", int(ip_hex, 16)))
    else:
        ip = inet_ntop(AF_INET6, bytes.fromhex(ip_hex))
    port = int(port_hex, 16)
    return ip, port


def read_proc_net(local_port=None, remote_port=None) -> InetInfoEntry | list[InetInfoEntry]:
    """Parse the /proc/net/{tcp/udp(6)} directories from
    procfs and gather the local and remote ip/ports connected
    to the system.
    """
    info = list()
    port_specified = any((local_port is not None, remote_port is not None))
    for prot in ('tcp', 'tcp6', 'udp', 'udp6'):
        with open(f'/proc/net/{prot}', 'r') as f:
            ipversion = '6' if prot[-1] == '6' else '4'
            for _, line in filter(lambda x: x[0] > 1, enumerate(f, start=1)):
                columns = line.split()
                lip, lp = parse_address(columns[1], ipversion)
                rip, rp = parse_address(columns[2], ipversion)
                if port_specified:
                    if any((
                        local_port is not None and local_port == lp,
                        remote_port is not None and remote_port == rp,
                    )):
                        return InetInfoEntry(lip, lp, rip, rp, prot)
                else:
                    info.append(InetInfoEntry(lip, lp, rip, rp, prot))
    return info
