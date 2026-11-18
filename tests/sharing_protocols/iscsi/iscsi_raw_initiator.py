"""
A minimal iSCSI initiator for the tests that need a PDU sequence libiscsi, and
so python-scsi, cannot send.

python-scsi and cython-iscsi cannot send a Logout (libiscsi only calls
iscsi_logout_sync() from its own utils and examples, and cython-iscsi does not
expose it), and they cannot choose DefaultTime2Retain or ErrorRecoveryLevel.
LIO puts a session into Time2Retain only when its last connection leaves by a
connection-level logout (reason code 1) or the session negotiated
ErrorRecoveryLevel 2. This module logs in with a chosen ISID and set of
operational keys and sends the connection-level logout, and does nothing else:
it sends no SCSI commands and answers no NOP-In, so its connection is only
good for logging in and out.

RFC 7143 section references are for the PDU layouts. No digests, no CHAP, a
single connection.
"""

import socket
import struct

OP_LOGIN_REQ = 0x03
OP_LOGIN_RSP = 0x23
OP_LOGOUT_REQ = 0x06
OP_LOGOUT_RSP = 0x26

CSG_SECURITY = 0
CSG_OPERATIONAL = 1
CSG_FULL_FEATURE = 3

LOGOUT_REASON_CLOSE_SESSION = 0
LOGOUT_REASON_CLOSE_CONNECTION = 1

# Operational keys proposed at login. DefaultTime2Retain and ErrorRecoveryLevel
# are overridden by the caller; the rest are what a typical initiator offers.
DEFAULT_KEYS = {
    "HeaderDigest": "None",
    "DataDigest": "None",
    "MaxRecvDataSegmentLength": "8192",
    "MaxConnections": "1",
    "InitialR2T": "Yes",
    "ImmediateData": "Yes",
    "MaxBurstLength": "262144",
    "FirstBurstLength": "65536",
    "DefaultTime2Wait": "2",
    "DefaultTime2Retain": "20",
    "MaxOutstandingR2T": "1",
    "DataPDUInOrder": "Yes",
    "DataSequenceInOrder": "Yes",
    "ErrorRecoveryLevel": "0",
}


class IscsiError(Exception):
    pass


def _encode_keys(keys):
    # No padding here: the data segment length in the BHS must not count it
    # (_send_pdu pads on the wire), or the target reads the pad bytes as empty keys.
    return b"".join(f"{k}={v}".encode() + b"\0" for k, v in keys.items())


def _decode_keys(data):
    out = {}
    for item in data.split(b"\0"):
        if b"=" in item:
            k, _, v = item.partition(b"=")
            out[k.decode()] = v.decode()
    return out


class RawInitiator:
    """One connection, one session. Use as a context manager; leaving the block
    closes the TCP connection (an abrupt drop unless logout_connection() ran).

    `isid` is 12 hex digits, as iscsi_ua_pr_utils.isid_en_hex() produces, so a
    later python-scsi login with the same initiator name and the matching
    isid_en qualifier is the same initiator port."""

    def __init__(self, host, target_iqn, initiator_name, isid, port=3260, keys=None, timeout=30):
        self.host = host
        self.target_iqn = target_iqn
        self.initiator_name = initiator_name
        self.isid = bytes.fromhex(isid)
        assert len(self.isid) == 6, isid
        self.port = port
        self.keys = {**DEFAULT_KEYS, **(keys or {})}
        self.timeout = timeout
        self.sock = None
        self.tsih = 0
        self.cid = 0
        self.itt = 1
        self.cmdsn = 1
        self.stat_sn = None  # StatSN of the last response; None before the first
        self.exp_cmd_sn = 1
        self.negotiated = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # -- wire ---------------------------------------------------------------

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise IscsiError(f"connection closed with {n - len(buf)} bytes outstanding")
            buf += chunk
        return buf

    def _recv_pdu(self):
        bhs = self._recv_exact(48)
        ahs_len = bhs[4] * 4
        data_len = int.from_bytes(bhs[5:8], "big")
        if ahs_len:
            self._recv_exact(ahs_len)
        data = self._recv_exact(data_len + (-data_len % 4))[:data_len]
        return bhs, data

    def _send_pdu(self, bhs, data=b""):
        assert len(bhs) == 48
        self.sock.sendall(bhs + data + b"\0" * (-len(data) % 4))

    def _exp_stat_sn(self):
        return 0 if self.stat_sn is None else (self.stat_sn + 1) & 0xFFFFFFFF

    # -- login --------------------------------------------------------------

    def _login_pdu(self, csg, nsg, transit, data):
        bhs = bytearray(48)
        bhs[0] = 0x40 | OP_LOGIN_REQ  # immediate, RFC 7143 11.12
        bhs[1] = (0x80 if transit else 0) | (csg << 2) | nsg
        bhs[2] = 0  # version-max
        bhs[3] = 0  # version-min
        bhs[5:8] = len(data).to_bytes(3, "big")
        bhs[8:14] = self.isid
        bhs[14:16] = struct.pack(">H", self.tsih)
        bhs[16:20] = struct.pack(">I", self.itt)
        bhs[20:22] = struct.pack(">H", self.cid)
        bhs[24:28] = struct.pack(">I", self.cmdsn)
        bhs[28:32] = struct.pack(">I", self._exp_stat_sn())
        return bytes(bhs)

    def _login_round(self, csg, nsg, keys):
        """Send one login PDU and read the response. Returns (flags, keys)."""
        data = _encode_keys(keys)
        self._send_pdu(self._login_pdu(csg, nsg, True, data), data)
        bhs, rdata = self._recv_pdu()
        if bhs[0] & 0x3F != OP_LOGIN_RSP:
            raise IscsiError(f"expected a Login Response, got opcode 0x{bhs[0] & 0x3F:02x}")
        status_class, status_detail = bhs[36], bhs[37]
        if status_class != 0:
            raise IscsiError(f"login refused: class {status_class} detail {status_detail}")
        if bhs[1] & 0x40:
            raise IscsiError("login response continues over several PDUs; not supported")
        self.tsih = struct.unpack(">H", bhs[14:16])[0]
        self.stat_sn = struct.unpack(">I", bhs[24:28])[0]
        self.exp_cmd_sn = struct.unpack(">I", bhs[28:32])[0]
        return bhs[1], _decode_keys(rdata)

    def login(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)
        flags, _ = self._login_round(
            CSG_SECURITY,
            CSG_OPERATIONAL,
            {
                "InitiatorName": self.initiator_name,
                "TargetName": self.target_iqn,
                "SessionType": "Normal",
                "AuthMethod": "None",
            },
        )
        if not (flags & 0x80) or (flags & 3) != CSG_OPERATIONAL:
            raise IscsiError(f"target did not move to the operational stage (flags 0x{flags:02x})")
        keys = dict(self.keys)
        for _ in range(8):
            flags, got = self._login_round(CSG_OPERATIONAL, CSG_FULL_FEATURE, keys)
            self.negotiated.update(got)
            if (flags & 0x80) and (flags & 3) == CSG_FULL_FEATURE:
                return self
            keys = {}  # the target has no more to ask; only the transit bit remains
        raise IscsiError("login did not complete")

    # -- logout -------------------------------------------------------------

    def logout_connection(self):
        """Send Logout with reason code 1 (close the connection) for this
        connection, the only one of the session, and read the response. The
        target then closes the TCP connection. Returns the response code (0:
        connection closed successfully)."""
        bhs = bytearray(48)
        bhs[0] = OP_LOGOUT_REQ  # not immediate: CmdSN is the expected one
        bhs[1] = 0x80 | LOGOUT_REASON_CLOSE_CONNECTION
        bhs[16:20] = struct.pack(">I", self.itt + 1)
        bhs[20:22] = struct.pack(">H", self.cid)
        bhs[24:28] = struct.pack(">I", self.exp_cmd_sn)
        bhs[28:32] = struct.pack(">I", self._exp_stat_sn())
        self._send_pdu(bytes(bhs))
        rsp, _ = self._recv_pdu()
        if rsp[0] & 0x3F != OP_LOGOUT_RSP:
            raise IscsiError(f"expected a Logout Response, got opcode 0x{rsp[0] & 0x3F:02x}")
        return rsp[2]

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None
