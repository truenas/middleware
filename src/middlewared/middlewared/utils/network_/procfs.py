from codecs import decode
from dataclasses import dataclass
from socket import inet_ntop, AF_INET, AF_INET6
from struct import pack, unpack

__all__ = ('read_proc_net',)


@dataclass(slots=True, frozen=True)
class InetInfoEntry:
    local_ip: str
    local_port: int
    remote_ip: str
    remote_port: int
    protocol: str


def hex_to_ipv6(hex_addr: str) -> str:
    """ hex address to standard IPv6 format
    Process:
        Convert hex to binary
        Unpack into 4 32-bit integers in network byte order
        Pack as 4 32-bit integers in native byte order
        Use inet_ntop (standard network API) to format the address
    """
    addr_bytes = decode(hex_addr, "hex")
    addr_tuple = unpack('!LLLL', addr_bytes)
    addr_packed = pack('@IIII', *addr_tuple)
    addr = inet_ntop(AF_INET6, addr_packed)
    return addr


def hex_to_ipv4(hex_addr: str) -> str:
    """ hex address to standard IPv4 format
    Process:
        Convert hex to binary (decode and unpack)
        Pack 32-bit integer in native byte order
        Use inet_ntop (standard network API) to format address
    """
    addr_int = int(hex_addr, 16)
    addr_packed = pack("=L", addr_int)
    addr = inet_ntop(AF_INET, addr_packed)
    return addr


def parse_address(hex_address: str, ipversion: str) -> tuple[str, int]:
    ip_hex, port_hex = hex_address.split(':')
    if ipversion == '4':
        ip = hex_to_ipv4(ip_hex)
    else:
        ip = hex_to_ipv6(ip_hex)
    port = int(port_hex, 16)
    return ip, port


def read_proc_net(local_port: int | None = None, remote_port: int | None = None) -> InetInfoEntry | list[InetInfoEntry]:
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
