import struct
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Dict, List, Optional

from .exceptions import MalformedPacketError


class ResponseStatus(Enum):
    SUCCESSFUL = 0
    UNKNOWN_ERROR = 1
    MESSAGE_FORMAT_ERROR = 2
    INVALID_REGISTRATION = 3
    RESERVED = 4
    INVALID_QUERY = 5
    SOURCE_UNKNOWN = 6
    SOURCE_ABSENT = 7
    SOURCE_UNAUTHORIZED = 8
    NO_SUCH_ENTRY = 9
    VERSION_NOT_SUPPORTED = 10
    INTERNAL_ERROR = 11
    BUSY = 12
    OPTION_NOT_UNDERSTOOD = 13
    INVALID_UPDATE = 14
    MESSAGE_NOT_SUPPORTED = 15
    SCN_EVENT_REJECTED = 16
    SCN_REGISTRATION_REJECTED = 17
    ATTRIBUTE_NOT_IMPLEMENTED = 18
    FC_DOMAIN_ID_NOT_AVAILABLE = 19
    FC_DOMAIN_ID_NOT_ALLOCATED = 20
    ESI_NOT_AVAILABLE = 21
    INVALID_DEREGISTRATION = 22
    REGISTRATION_FEATURE_NOT_SUPPORTED = 23


@dataclass
class iSNSPFlags(object):
    client: bool = False
    server: bool = False
    auth: bool = False
    replace: bool = False
    last: bool = False
    first: bool = False

    @property
    def int(self):
        val = 0
        val |= 0x8000 if self.client else 0
        val |= 0x4000 if self.server else 0
        val |= 0x2000 if self.auth else 0
        val |= 0x1000 if self.replace else 0
        val |= 0x0800 if self.last else 0
        val |= 0x0400 if self.first else 0
        return val

    @property
    def asbytes(self):
        return self.int.to_bytes(2, byteorder='big')

    @classmethod
    def from_val(cls, val: int):
        client = (val & 0x8000) == 0x8000
        server = (val & 0x4000) == 0x4000
        auth = (val & 0x2000) == 0x2000
        replace = (val & 0x1000) == 0x1000
        last = (val & 0x0800) == 0x0800
        first = (val & 0x0400) == 0x0400
        return cls(client, server, auth, replace, last, first)


@dataclass
class iSNSPAttribute(object):
    """
    This class models a iSNSP attribute which is contained in a iSNSP packet's
    payload. From RFC 4171:

    Byte   MSb                                        LSb
    Offset 0                                           31
           +--------------------------------------------+
         0 |               Attribute Tag                | 4 Bytes
           +--------------------------------------------+
         4 |            Attribute Length (N)            | 4 Bytes
           +--------------------------------------------+
         8 |                                            |
           |              Attribute Value               | N Bytes
           |                                            |
           +--------------------------------------------+
                    Total Length = 8 + N
    """
    tag: str     # 4 octets
    length: int  # 4 octets
    val: bytes

    tag_map: ClassVar[Dict[int, str]] = {
        0: 'Delimiter',
        1: 'Entity Identifier',
        2: 'Entity Protocol',
        3: 'Management IP Address',
        4: 'Timestamp',
        5: 'Protocol Version Range',
        6: 'Registration Period',
        7: 'Entity Index',
        8: 'Entity Next Index',
        11: 'Entity ISAKMP Phase-1',
        12: 'Entity Certificate',
        16: 'Portal IP Address',
        17: 'Portal TCP/UDP Port',
        18: 'Portal Symbolic Name',
        19: 'ESI Interval',
        20: 'ESI Port',
        22: 'Portal Index',
        23: 'SCN Port',
        24: 'Portal Next Index',
        27: 'Portal Security Bitmap',
        28: 'Portal ISAKMP Phase-1',
        29: 'Portal ISAKMP Phase-2',
        31: 'Portal Certificate',
        32: 'iSCSI Name',
        33: 'iSCSI Node Type',
        34: 'iSCSI Alias',
        35: 'iSCSI SCN Bitmap',
        36: 'iSCSI Node Index',
        37: 'WWNN Token',
        38: 'iSCSI Node Next Index',
        42: 'iSCSI AuthMethod',
        48: 'PG iSCSI Name',
        49: 'PG Portal IP Addr',
        50: 'PG Portal TCP/UDP Port',
        51: 'PG Tag (PGT)',
        52: 'PG Index',
        53: 'PG Next Index',
        64: 'FC Port Name WWPN',
        65: 'Port ID',
        66: 'FC Port Type',
        67: 'Symbolic Port Name',
        68: 'Fabric Port Name',
        69: 'Hard Address',
        70: 'Port IP-Address',
        71: 'Class of Service',
        72: 'FC-4 Types',
        73: 'FC-4 Descriptor',
        74: 'FC-4 Features',
        75: 'iFCP SCN bitmap',
        76: 'Port Role',
        77: 'Permanent Port Name',
        95: 'FC-4 Type Code',
        96: 'FC Node Name WWNN',
        97: 'Symbolic Node Name',
        98: 'Node IP-Address',
        99: 'Node IPA',
        101: 'Proxy iSCSI Name',
        128: 'Switch Name',
        129: 'Preferred ID',
        130: 'Assigned ID',
        131: 'Virtual_Fabric_ID',
        256: 'iSNS Server Vendor OUI',
        2049: 'DD_Set ID',
        2050: 'DD_Set Sym Name',
        2051: 'DD_Set Status',
        2052: 'DD_Set_Next_ID',
        2065: 'DD_ID',
        2066: 'DD_Symbolic Name',
        2067: 'DD_Member iSCSI Index',
        2068: 'DD_Member iSCSI Name',
        2069: 'DD_Member FC Port Name',
        2070: 'DD_Member Portal Index',
        2071: 'DD_Member Portal IP Addr',
        2072: 'DD_Member Portal TCP/UDP',
        2078: 'DD_Features',
        2079: 'DD_ID Next ID',
    }

    inv_tag_map: ClassVar[Dict[str, int]] = {v: k for k, v in tag_map.items()}
    packet_fmt: ClassVar[str] = '!LL'
    variable_length: ClassVar[List[int]] = [1, 11, 12, 18, 28, 29, 31, 32, 34,
                                            42, 48, 67, 73, 97, 101, 131, 2050,
                                            2066, 2068]
    string_attrs: ClassVar[List[int]] = [1, 18, 32, 34, 48, 67, 73, 97, 101,
                                         131, 2050, 2066, 2068]

    @property
    def asbytes(self):
        tagval = self.inv_tag_map[self.tag]
        if tagval in self.variable_length:
            # Were we passed in a string?
            if isinstance(self.val, str):
                data = bytearray(self.val, 'utf-8')
            elif isinstance(self.val, bytes):
                data = bytearray(self.val)
            elif isinstance(self.val, bytearray):
                data = self.val
            else:
                raise ValueError('Invalid type for value')
            # Terminate if necessary
            if len(data):
                if data[len(data) - 1] != 0:
                    data += b'\0'
            # Pad as necessary
            while len(data) % 4 != 0:
                data += b'\0'
        else:
            data = self.val
        self.length = len(data)
        packet_head = [
            tagval,
            self.length,
        ]
        encoded_packet = struct.pack(self.packet_fmt, *packet_head)
        encoded_packet += data
        return encoded_packet

    @classmethod
    def from_bytes(cls, packet: bytes):
        """
        Given a iSNSP attribute in bytes / wire format return a iSNSPAttribute
        object.
        """
        try:
            decoded_packet = [
                field.rstrip(b'\x00') if isinstance(field, bytes) else field
                for field in struct.unpack(
                    cls.packet_fmt, packet[:8]
                )
            ]
        except Exception as e:
            raise MalformedPacketError(f'Unable to parse iSNSP attribute: {e}')

        data = packet[8: 8 + decoded_packet[1]]
        if decoded_packet[0] in cls.string_attrs:
            data = data.decode('utf-8').rstrip('\x00')
        decoded_packet[0] = cls.tag_map[decoded_packet[0]]
        decoded_packet.append(data)
        return cls(*decoded_packet)

    @classmethod
    def Delimiter(cls):
        """
        Convenient constructor for a iSNSP Delimiter attr.
        """
        return cls(
            'Delimiter',
            0,
            bytes())

    @classmethod
    def iSCSIName(cls, name):
        """
        Convenient constructor for a iSNSP iSCSI Name attr.
        """
        return cls(
            'iSCSI Name',
            0,
            name)

    @classmethod
    def EntityIdentifier(cls, name):
        """
        Convenient constructor for a iSNSP Entity Identifier attr.
        """
        return cls(
            'Entity Identifier',
            0,
            name)

    @classmethod
    def PortalIPAddress(cls, name):
        """
        Convenient constructor for a iSNSP Portal IP Address attr.
        """
        return cls(
            'Portal IP Address',
            0,
            name)

    @classmethod
    def iSCSINodeType(cls, val):
        """
        Convenient constructor for a iSCSI Node Type attr.
        """
        return cls(
            'iSCSI Node Type',
            4,
            val.to_bytes(4, byteorder='big'))


@dataclass
class iSNSPPacket(object):
    """
    This class models a iSNSP packet. From RFC 4171:

    Byte   MSb                                        LSb
    Offset 0                   15 16                   31
           +---------------------+----------------------+
         0 |   iSNSP VERSION     |    FUNCTION ID       | 4 Bytes
           +---------------------+----------------------+
         4 |     PDU LENGTH      |       FLAGS          | 4 Bytes
           +---------------------+----------------------+
         8 |   TRANSACTION ID    |    SEQUENCE ID       | 4 Bytes
           +---------------------+----------------------+
        12 |                                            |
           |                PDU PAYLOAD                 | N Bytes
           |                    ...                     |
           +--------------------------------------------+
      12+N | AUTHENTICATION BLOCK (Multicast/Broadcast) | L Bytes
           +--------------------------------------------+
                    Total Length = 12 + N + L
    """
    version: int        # 2 octets - 0x0001
    function: str       # 2 octets
    pdulen: int         # 2 octets
    flags: iSNSPFlags   # 2 octets
    txnid: int          # 2 octets - a unique value for each concurrently
    #                                outstanding request message.
    seqid: int          # 2 octets - unique value for each PDU within a single
    #                                transaction.  The SEQUENCE_ID value of the
    #                                first PDU transmitted in a given iSNS
    #                                message MUST be zero (0), and each
    #                                SEQUENCE_ID value in each PDU MUST be
    #                                numbered sequentially in the order in
    #                                which the PDUs are transmitted.
    payload: list[iSNSPAttribute]
    payload_offset: ClassVar[int] = 12
    packet_fmt: ClassVar[str] = '!HHHHHH'
    func_map: ClassVar[Dict[int, str]] = {
        0x0001: 'DevAttrReg',
        0x0002: 'DevAttrQry',
        0x0003: 'DevGetNext',
        0x0004: 'DevDereg',
        0x0005: 'SCNReg',
        0x0006: 'SCNDereg',
        0x0007: 'SCNEvent',
        0x0008: 'SCN',
        0x0009: 'DDReg',
        0x000A: 'DDDereg',
        0x000B: 'DDSReg',
        0x000C: 'DDSDereg',
        0x000D: 'ESI',
        0x000E: 'Heartbeat',
        0x0011: 'RqstDomId',
        0x0012: 'RlseDomId',
        0x0013: 'GetDomId',
        0x8001: 'DevAttrRegRsp',
        0x8002: 'DevAttrQryRsp',
        0x8003: 'DevGetNextRsp',
        0x8004: 'DevDeregRsp',
        0x8005: 'SCNRegRsp',
        0x8006: 'SCNDeregRsp',
        0x8007: 'SCNEventRsp',
        0x8008: 'SCNRsp',
        0x8009: 'DDRegRsp',
        0x800A: 'DDDeregRsp',
        0x800B: 'DDSRegRsp',
        0x800C: 'DDSDeregRsp',
        0x800D: 'ESIRsp',
        0x8011: 'RqstDomIdRsp',
        0x8012: 'RlseDomIdRsp',
        0x8013: 'GetDomIdRsp',
    }

    ifunc_map: ClassVar[Dict[str, int]] = {v: k for k, v in func_map.items()}

    HEADER_LENGTH = 12

    @property
    def asbytes(self):
        payload_bytes = bytes()
        for attr in self.payload:
            payload_bytes += attr.asbytes
        self.pdulen = len(payload_bytes)
        packet_head = [
            self.version,
            self.ifunc_map[self.function],
            self.pdulen,
            self.flags.int,
            self.txnid,
            self.seqid,
        ]
        encoded_packet = struct.pack(self.packet_fmt, *packet_head)
        encoded_packet += payload_bytes
        return encoded_packet

    @property
    def msg_type(self) -> Optional[str]:
        if msg_type_option := self.options.by_code(53):
            return list(msg_type_option.value.values())[0]
        else:
            return None

    @classmethod
    def pdu_length(cls, packet: bytes):
        try:
            decoded_packet = [
                field.rstrip(b'\x00') if isinstance(field, bytes) else field
                for field in struct.unpack(
                    cls.packet_fmt, packet[: cls.payload_offset]
                )
            ]
        except Exception as e:
            raise MalformedPacketError(f'Unable to parse iSNSP packet: {e}')
        return decoded_packet[2]

    @classmethod
    def from_bytes(cls, packet: bytes):
        """
        Given a iSNSP packet in bytes / wire format return a iSNSPPacket
        object.
        """
        try:
            decoded_packet = [
                field.rstrip(b'\x00') if isinstance(field, bytes) else field
                for field in struct.unpack(
                    cls.packet_fmt, packet[: cls.payload_offset]
                )
            ]
        except Exception as e:
            raise MalformedPacketError(f'Unable to parse iSNSP packet: {e}')

        # Decode the function
        # decoded_packet[0] = cls.op_map[decoded_packet[0]]
        decoded_packet[1] = cls.func_map[decoded_packet[1]]
        flags = iSNSPFlags.from_val(decoded_packet[3])
        decoded_packet[3] = flags

        # Handle payload
        _data = packet[cls.payload_offset:]
        payload = []
        # If this is a response from the server, then the first part of the
        # payload is the status.
        if flags.server:
            payload.append(ResponseStatus(int.from_bytes(_data[:4], 'big')))
            _data = _data[4:]
        while _data:
            attr = iSNSPAttribute.from_bytes(_data)
            _data = _data[8 + attr.length:]
            payload.append(attr)
        decoded_packet.append(payload)

        return cls(*decoded_packet)

    @classmethod
    def DevGetNext(
        cls,
        flags: iSNSPFlags,
        txnid: int,
        seqid: int,
        payload: list[iSNSPAttribute],
    ):
        """
        Convenient constructor for a iSNSP DevGetNext packet.
        """
        return cls(
            1,
            'DevGetNext',
            0,
            flags,
            txnid,
            seqid,
            payload)

    @classmethod
    def DevAttrQry(
        cls,
        flags: iSNSPFlags,
        txnid: int,
        seqid: int,
        payload: list[iSNSPAttribute],
    ):
        """
        Convenient constructor for a iSNSP DevAttrQry packet.
        """
        return cls(
            1,
            'DevAttrQry',
            0,
            flags,
            txnid,
            seqid,
            payload)

    @classmethod
    def DevAttrReg(
        cls,
        flags: iSNSPFlags,
        txnid: int,
        seqid: int,
        payload: list[iSNSPAttribute],
    ):
        """
        Convenient constructor for a iSNSP DevAttrReg packet.
        """
        return cls(
            1,
            'DevAttrReg',
            0,
            flags,
            txnid,
            seqid,
            payload)

    @classmethod
    def DevDereg(
        cls,
        flags: iSNSPFlags,
        txnid: int,
        seqid: int,
        payload: list[iSNSPAttribute],
    ):
        """
        Convenient constructor for a iSNSP DevDereg packet.
        """
        return cls(
            1,
            'DevDereg',
            0,
            flags,
            txnid,
            seqid,
            payload)
