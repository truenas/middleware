import dataclasses
import select
import socket
import struct
import time

from middlewared.utils import run
from middlewared.utils.threading import start_daemon_thread


# Netlink constants
AF_NETLINK = 16
NETLINK_ROUTE = 0

# RTM message types
RTM_NEWLINK = 16
RTM_GETLINK = 18
RTM_NEWADDR = 20
RTM_DELADDR = 21
RTM_GETADDR = 22

# Netlink flags
NLM_F_REQUEST = 0x01
NLM_F_DUMP = 0x300
NLM_F_ACK = 0x04


# Message types
NLMSG_DONE = 3
NLMSG_ERROR = 2

# Netlink groups for address monitoring
RTNLGRP_IPV4_IFADDR = 5
RTNLGRP_IPV6_IFADDR = 9

# Interface flags
IFF_UP = 0x1
IFF_BROADCAST = 0x2
IFF_LOOPBACK = 0x8
IFF_POINTOPOINT = 0x10
IFF_RUNNING = 0x40
IFF_NOARP = 0x100
IFF_PROMISC = 0x200
IFF_MULTICAST = 0x1000

# Attribute types
IFLA_IFNAME = 3
IFA_ADDRESS = 1
IFA_LOCAL = 2
IFA_LABEL = 3
IFA_BROADCAST = 4


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class NetlinkMessage:
    """Netlink message header"""

    length: int
    type: int
    flags: int
    seq: int
    pid: int
    payload: bytes


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class IfAddrMessage:
    """Interface address message"""

    family: int
    prefixlen: int
    flags: int
    scope: int
    index: int
    attributes: dict


def parse_netlink_message(data):
    """Parse netlink message header"""
    expected_size = 16
    if len(data) < expected_size:
        raise ValueError("Message too short")

    # struct nlmsghdr
    length, msg_type, flags, seq, pid = struct.unpack("IHHII", data[:expected_size])
    payload = data[expected_size:length] if length > 16 else b""
    return NetlinkMessage(
        length=length, type=msg_type, flags=flags, seq=seq, pid=pid, payload=payload
    )


def _parse_attributes(data):
    """Parse rtattr structures"""
    attrs = {}
    offset = 0
    while offset + 4 <= len(data):
        # struct rtattr: length (2 bytes), type (2 bytes)
        attr_len, attr_type = struct.unpack("HH", data[offset:offset + 4])
        if attr_len < 4:
            break

        # Payload starts after the 4-byte header
        if offset + attr_len > len(data):
            break

        payload = data[offset + 4:offset + attr_len]
        attrs[attr_type] = payload

        # Move to next attribute (align to 4 bytes)
        offset += (attr_len + 3) & ~3
    return attrs


def parse_ifaddr_message(data, start_offset=0, end_offset=None):
    """Parse ifaddrmsg structure"""
    if end_offset is None:
        end_offset = len(data)

    slice_data = data[start_offset:end_offset]
    if len(slice_data) < 8:
        raise ValueError("IfAddr message too short")

    # struct ifaddrmsg
    family, prefixlen, flags, scope, index = struct.unpack("BBBBI", slice_data[:8])
    return IfAddrMessage(
        family=family,
        prefixlen=prefixlen,
        flags=flags,
        scope=scope,
        index=index,
        attributes=_parse_attributes(slice_data[8:]),
    )


def format_address(family, addr_data):
    """Format IP address from binary data"""
    if family == socket.AF_INET and len(addr_data) == 4:
        return socket.inet_ntop(socket.AF_INET, addr_data)
    elif family == socket.AF_INET6 and len(addr_data) == 16:
        return socket.inet_ntop(socket.AF_INET6, addr_data)
    else:
        return addr_data.hex()


def send_netlink_request(sock, msg_type, family=socket.AF_UNSPEC, interface_index=0):
    """Send a netlink request using existing socket"""
    # Build netlink message
    if msg_type == RTM_GETLINK:
        # ifinfomsg structure: family, pad, type, index, flags, change
        msg_data = struct.pack("BBHiII", family, 0, 0, interface_index, 0, 0)
    elif msg_type == RTM_GETADDR:
        # ifaddrmsg structure
        msg_data = struct.pack("BBBBI", family, 0, 0, 0, interface_index)
    else:
        msg_data = b""

    # Netlink header
    nlh_len = 16 + len(msg_data)  # nlmsghdr is 16 bytes
    nlh_type = msg_type
    nlh_flags = NLM_F_REQUEST | NLM_F_DUMP
    nlh_seq = 1
    nlh_pid = 0
    nlh = struct.pack("IHHII", nlh_len, nlh_type, nlh_flags, nlh_seq, nlh_pid)
    message = nlh + msg_data
    sock.send(message)
    return nlh_seq


def receive_netlink_response(sock, expected_seq=None):
    """Receive and parse netlink response"""
    messages = []
    while True:
        data = sock.recv(65536)
        offset = 0
        while offset < len(data):
            if offset + 16 > len(data):
                break

            # Parse netlink header
            try:
                msg = parse_netlink_message(data[offset:])
            except ValueError:
                break

            if msg.type == NLMSG_DONE:
                return messages
            elif msg.type == NLMSG_ERROR:
                # Check for errors
                error_code = struct.unpack("i", data[offset + 16:offset + 20])[0]
                if error_code != 0:
                    raise Exception(f"Netlink error: {error_code}")
                offset += msg.length
                continue

            # Extract message payload if sequence matches (or no sequence check)
            if expected_seq is None or msg.seq == expected_seq:
                messages.append((msg.type, msg.payload))

            # Move to next message (align to 4 bytes)
            offset += (msg.length + 3) & ~3
    return messages


def parse_netlink_attributes(data, offset):
    """Parse netlink attributes from data starting at offset"""
    attrs = {}
    while offset < len(data):
        if offset + 4 > len(data):
            break

        # Parse attribute header (rta_len, rta_type)
        rta_len, rta_type = struct.unpack("HH", data[offset:offset + 4])

        if rta_len < 4 or offset + rta_len > len(data):
            break

        # Extract attribute data
        attr_data = data[offset + 4:offset + rta_len]
        attrs[rta_type] = attr_data

        # Move to next attribute (align to 4 bytes)
        offset += (rta_len + 3) & ~3
    return attrs


def get_interface_addresses(sock, interface_index):
    """Get all IP addresses for a specific interface using existing netlink socket"""
    try:
        addresses = []
        # Get address information for IPv4 and IPv6
        for family in (socket.AF_INET, socket.AF_INET6):
            seq = send_netlink_request(sock, RTM_GETADDR, family, 0)
            messages = receive_netlink_response(sock, seq)
            for msg_type, msg_data in messages:
                if msg_type == RTM_NEWADDR and len(msg_data) >= 8:
                    # Parse ifaddrmsg
                    ifa_msg = parse_ifaddr_message(msg_data)
                    if ifa_msg.index == interface_index:
                        # Get address (prefer LOCAL over ADDRESS)
                        addr_data = None
                        if IFA_LOCAL in ifa_msg.attributes:
                            addr_data = ifa_msg.attributes[IFA_LOCAL]
                        elif IFA_ADDRESS in ifa_msg.attributes:
                            addr_data = ifa_msg.attributes[IFA_ADDRESS]

                        if addr_data:
                            if ifa_msg.family == socket.AF_INET:
                                addr = socket.inet_ntop(socket.AF_INET, addr_data)
                                addresses.append(f"{addr}/{ifa_msg.prefixlen}")
                            elif ifa_msg.family == socket.AF_INET6:
                                addr = socket.inet_ntop(socket.AF_INET6, addr_data)
                                addresses.append(f"{addr}/{ifa_msg.prefixlen}")
        return addresses
    except Exception:
        # Return empty list on any error
        return []


def get_interface_name(sock, index):
    """Get interface name from index via netlink"""
    try:
        seq = send_netlink_request(sock, RTM_GETLINK, socket.AF_UNSPEC, 0)
        messages = receive_netlink_response(sock, seq)
        for msg_type, msg_data in messages:
            if msg_type == RTM_NEWLINK and len(msg_data) >= 16:
                # Parse ifinfomsg
                _, _, _, interface_index, _, _ = struct.unpack("BBHiII", msg_data[:16])
                if interface_index == index:
                    # Parse attributes
                    attrs = parse_netlink_attributes(msg_data, 16)
                    if IFLA_IFNAME in attrs:
                        return attrs[IFLA_IFNAME].rstrip(b"\x00").decode("utf-8")
    except Exception:
        pass

    return None


def create_address_event(sock, msg_type, ifa_msg, ip_addr, if_name):
    """Create event data dictionary for IP address changes"""
    if ifa_msg.family == socket.AF_INET:
        family = "inet"
    elif ifa_msg.family == socket.AF_INET6:
        family = "inet6"
    else:
        family = f"family_{ifa_msg.family}"

    # Get all current IP addresses for this interface
    available_ips = get_interface_addresses(sock, ifa_msg.index)
    # Extract just the IP addresses without prefixes for the available_ips list
    ip_addresses_only = []
    for addr in available_ips:
        if "/" in addr:
            ip_addresses_only.append(addr.split("/")[0])
        else:
            ip_addresses_only.append(addr)

    event_data = {
        "iface": if_name,
        "ip": f"{ip_addr}/{ifa_msg.prefixlen}",
        "event": "remove" if msg_type == RTM_DELADDR else "add",
        "family": family,
        "scope": ifa_msg.scope,
        "index": ifa_msg.index,
        "broadcast": None,
        "available_ips": ip_addresses_only,
    }
    if brd := ifa_msg.attributes.get(IFA_BROADCAST):
        # Add broadcast address if available
        event_data["broadcast"] = format_address(ifa_msg.family, brd)
    return event_data


def process_netlink_data(sock, data):
    """Process netlink data and yield IP address change events"""
    offset = 0
    while offset < len(data):
        try:
            msg = parse_netlink_message(data[offset:])

            # Only process address messages
            if msg.type in (RTM_NEWADDR, RTM_DELADDR):
                ifa_msg = parse_ifaddr_message(msg.payload)

                # Get interface name from IFA_LABEL attribute or fallback to netlink query
                if_name = None
                if IFA_LABEL in ifa_msg.attributes:
                    if_name = (
                        ifa_msg.attributes[IFA_LABEL].rstrip(b"\x00").decode("utf-8")
                    )
                else:
                    if_name = get_interface_name(sock, ifa_msg.index)

                # Get address
                local_addr = ifa_msg.attributes.get(IFA_LOCAL)
                addr = ifa_msg.attributes.get(IFA_ADDRESS)

                # Use LOCAL if available, otherwise ADDRESS
                ip_addr = None
                if local_addr:
                    ip_addr = format_address(ifa_msg.family, local_addr)
                elif addr:
                    ip_addr = format_address(ifa_msg.family, addr)

                if ip_addr:
                    yield create_address_event(
                        sock, msg.type, ifa_msg, ip_addr, if_name
                    )

            # Move to next message
            offset += (msg.length + 3) & ~3  # Align to 4 bytes

        except (ValueError, struct.error):
            break

        if offset >= len(data) or msg.length == 0:
            break


def netlink_events(middleware):
    """Monitor netlink events for IP address changes"""
    sock = None
    poller = None
    retry_count = 0
    max_retries = 10
    while True:
        try:
            if sock is None:
                # Create netlink socket
                sock = socket.socket(AF_NETLINK, socket.SOCK_RAW, NETLINK_ROUTE)

                # Calculate groups mask (bit positions for multicast groups)
                groups = 1 << (RTNLGRP_IPV4_IFADDR - 1)
                groups |= 1 << (RTNLGRP_IPV6_IFADDR - 1)

                # Bind to groups
                sock.bind((0, groups))
                retry_count = 0  # Reset retry count on successful socket creation
                middleware.logger.trace(
                    "Netlink socket created successfully for IP address monitoring"
                )
                # Create poller for the new socket
                poller = select.poll()
                poller.register(sock, select.POLLIN)

            # Wait for messages
            events = poller.poll()  # Blocks indefinitely until socket is ready
            if events:
                data = sock.recv(8192)

                # Process netlink data and send events
                for event_data in process_netlink_data(sock, data):
                    middleware.send_event(
                        "ipaddress.change", "CHANGED", fields=event_data
                    )
        except Exception:
            middleware.logger.error("Netlink monitoring failed", exc_info=True)

            # Close socket on error
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
                sock = None
                poller = None

            retry_count += 1
            if retry_count >= max_retries:
                middleware.logger.warning(
                    f"Failed to create netlink socket after {max_retries} attempts. "
                    "IP address monitoring may not work properly."
                )
                retry_count = 0  # Reset counter to continue trying

            time.sleep(5)  # Wait before retry


async def _systemctl_restart_ixvendor(middleware):
    if await middleware.call("system.vendor.is_vendored"):
        await run(["systemctl", "restart", "ix-vendor"], check=False)


async def _restart_vendor_service(middleware, event_type, args):
    middleware.create_task(_systemctl_restart_ixvendor(middleware))


def setup(middleware):
    # Register the IP address change event
    middleware.event_register(
        "ipaddress.change", "Sent when IP addresses change on a NIC", private=True
    )
    middleware.event_subscribe("ipaddress.change", _restart_vendor_service)
    # Start the netlink monitoring daemon thread
    start_daemon_thread(name="netlink_events", target=netlink_events, args=(middleware,))
