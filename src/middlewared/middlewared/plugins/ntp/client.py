from __future__ import annotations

import dataclasses
import socket
import struct
import time
from typing import Any


def format_ntp_packet(data: bytes) -> dict[str, Any]:
    # unpack the response
    unpacked = struct.unpack('!B B B b 11I', data)

    recv_timestamp = unpacked[11] + float(unpacked[12]) / 2 ** 32
    ntp_time = recv_timestamp - 2208988800  # NTP timestamp starts from 1st January 1900
    recv_utc_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ntp_time))
    return {
        'leap': unpacked[0] >> 6 & 0x7,
        'version': unpacked[0] >> 3 & 0x7,
        'mode': unpacked[0] & 0x7,
        'stratum': unpacked[1],
        'poll': unpacked[2],
        'precision': unpacked[3],
        'root_delay': float(unpacked[4]) / 2 ** 16,
        'root_dispersion': float(unpacked[5]) / 2 ** 16,
        'ref_id': unpacked[6],
        'ref_timestamp': unpacked[7] + float(unpacked[8]) / 2 ** 32,
        'orig_timestamp': unpacked[9] + float(unpacked[10]) / 2 ** 32,
        'recv_timestamp': recv_timestamp,
        'recv_timestamp_formatted': recv_utc_time,
        'tx_timestamp': unpacked[13] + float(unpacked[14]) / 2 ** 32,
    }


@dataclasses.dataclass(slots=True)
class NTPClient:
    host: str
    timeout: int = 5  # second

    def make_request(self) -> dict[str, Any]:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # set timeout
            s.settimeout(self.timeout)

            # send a ntp formatted packet
            s.sendto(b'\x1b' + 47 * b'\0', (self.host, 123))

            # receive response from ntp peer
            data, addr = s.recvfrom(1024)

            # format the received data
            return format_ntp_packet(data)
