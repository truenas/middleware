import contextlib

from middlewared.test.integration.utils import call
from .ftp_proto import ftp_connect, ftp_connection, ftps_connect, ftps_connection  # noqa
from .iscsi_proto import ISCSIDiscover, initiator_name_supported, iscsi_scsi_connect, iscsi_scsi_connection  # noqa
from .iSNSP.client import iSNSPClient
from .ms_rpc import MS_RPC  # noqa
from .nfs_proto import SSH_NFS  # noqa
from .smb_proto import SMB


@contextlib.contextmanager
def smb_connection(**kwargs):
    c = SMB()
    c.connect(**kwargs)

    try:
        yield c
    finally:
        c.disconnect()


@contextlib.contextmanager
def smb_share(path: str, options: dict | None = None):
    share_id = call("sharing.smb.create", {"path": path, **(options or {})})["id"]

    try:
        yield share_id
    finally:
        call("sharing.smb.delete", share_id)


@contextlib.contextmanager
def nfs_share(path: str, options: dict | None = None):
    share_id = call("sharing.nfs.create", {"path": path, **(options or {})})["id"]

    try:
        yield share_id
    finally:
        call("sharing.nfs.delete", share_id)


@contextlib.contextmanager
def isns_connection(host, initiator_iqn, **kwargs):
    c = iSNSPClient(host, initiator_iqn, **kwargs)
    try:
        c.connect()
        c.register_initiator()
        yield c
    finally:
        c.deregister_initiator()
        c.close()
