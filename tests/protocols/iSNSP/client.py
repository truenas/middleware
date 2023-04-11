import socket

from .exceptions import *
from .packet import *


class iSNSPClient(object):
    def __init__(self, host, initiator_iqn, port=3205):
        self.host = host
        if initiator_iqn:
            self.source = iSNSPAttribute.iSCSIName(initiator_iqn)
        else:
            self.source = None
        self.port = port
        self.txnid = 1
        self.sock = None

    def connect(self, timeout=10):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        if timeout:
            self.sock.settimeout(timeout)

    def close(self):
        if self.sock:
            self.sock.close()

    def register_initiator(self, iqn=None):
        if not self.source:
            self.source = iSNSPAttribute.iSCSIName(iqn)
        eid = iSNSPAttribute.EntityIdentifier('')
        delimiter = iSNSPAttribute.Delimiter()
        iscsi_name = iSNSPAttribute.iSCSIName(iqn) if iqn else self.source
        node_type = iSNSPAttribute.iSCSINodeType(2)
        flags = iSNSPFlags(client=True, first=True, last=True)

        pkt = iSNSPPacket.DevAttrReg(flags, self.txnid, 0,
                                     [self.source, eid, delimiter, iscsi_name,
                                      node_type])
        rpkt = self.send_packet(pkt)
        if rpkt.function != 'DevAttrRegRsp':
            raise iSNSPException('Invalid response type', response)

    def list_targets(self, verbose=False):
        result = []
        next_iscsi_name = iSNSPAttribute.iSCSIName('')
        delimiter = iSNSPAttribute.Delimiter()
        target_node_type = iSNSPAttribute.iSCSINodeType(1)
        flags = iSNSPFlags(client=True, first=True, last=True)
        while True:
            pkt = iSNSPPacket.DevGetNext(flags, self.txnid, 0,
                                         [self.source,
                                          next_iscsi_name,
                                          delimiter,
                                          target_node_type])
            try:
                rpkt = self.send_packet(pkt)
                if verbose:
                    for p in rpkt.payload:
                        print(p)
                if rpkt.payload[1].tag == 'iSCSI Name':
                    next_iscsi_name = rpkt.payload[1]
                    result.append(next_iscsi_name.val)
                else:
                    raise iSNSPException('Invalid response attribute', rpkt)
            except StopIteration:
                break
        return result

    def fetch_eids(self, verbose=False):
        result = []
        eid = iSNSPAttribute.EntityIdentifier(bytes())
        delimiter = iSNSPAttribute.Delimiter()
        flags = iSNSPFlags(client=True, first=True, last=True)
        while True:
            pkt = iSNSPPacket.DevGetNext(flags, self.txnid, 0,
                                         [self.source, eid, delimiter])
            try:
                rpkt = self.send_packet(pkt)
                if verbose:
                    for p in rpkt.payload:
                        print(p)
                if rpkt.payload[1].tag == 'Entity Identifier':
                    eid = rpkt.payload[1]
                    result.append(eid)
                else:
                    raise iSNSPException('Invalid response attribute', rpkt)
            except StopIteration:
                break
        return result

    def deregister_initiator(self, iqn=None):
        delimiter = iSNSPAttribute.Delimiter()
        flags = iSNSPFlags(client=True, first=True, last=True)
        iscsi_name = iSNSPAttribute.iSCSIName(iqn) if iqn else self.source
        pkt = iSNSPPacket.DevDereg(flags, self.txnid, 0,
                                   [self.source, delimiter, iscsi_name])
        rpkt = self.send_packet(pkt)
        if rpkt.function != 'DevDeregRsp':
            raise iSNSPException('Invalid response type', response)

    def send(self, msg, msglen):
        totalsent = 0
        while totalsent < msglen:
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent

    def recv_packet(self):
        length_calculated = False
        chunks = []
        bytes_required = iSNSPPacket.HEADER_LENGTH
        bytes_received = 0
        while bytes_received < bytes_required:
            chunk = self.sock.recv(min(bytes_required - bytes_received, 4096))
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            chunks.append(chunk)
            bytes_received = bytes_received + len(chunk)
            if not length_calculated and bytes_received >= iSNSPPacket.HEADER_LENGTH:
                pdu_len = iSNSPPacket.pdu_length(b''.join(chunks))
                length_calculated = True
                bytes_required = iSNSPPacket.HEADER_LENGTH + pdu_len
        return b''.join(chunks)

    def send_packet(self, pkt):
        msg = pkt.asbytes
        self.send(msg, len(msg))
        data = self.recv_packet()
        _txnid = self.txnid
        self.txnid += 1
        response = iSNSPPacket.from_bytes(data)
        status = response.payload[0]
        if status == ResponseStatus.NO_SUCH_ENTRY:
            raise StopIteration
        if status != ResponseStatus.SUCCESSFUL:
            raise iSNSPException('Invalid response', status)
        if response.txnid != _txnid:
            raise iSNSPException('Invalid response txnid', response)
        return response
