import contextlib

from functions import DELETE, POST

from .iscsi_proto import iscsi_scsi_connect, iscsi_scsi_connection
from .iSNSP.client import iSNSPClient
from .nfs_proto import SSH_NFS
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
def smb_share(path, options=None):
    results = POST("/sharing/smb/", {
        "path": path,
        **(options or {}),
    })
    assert results.status_code == 200, results.text
    id = results.json()["id"]

    try:
        yield id
    finally:
        result = DELETE(f"/sharing/smb/id/{id}/")
        assert result.status_code == 200, result.text


@contextlib.contextmanager
def nfs_share(path, options=None):
    results = POST("/sharing/nfs/", {
        "path": path,
        **(options or {}),
    })
    assert results.status_code == 200, results.text
    id = results.json()["id"]

    try:
        yield id
    finally:
        result = DELETE(f"/sharing/nfs/id/{id}/")
        assert result.status_code == 200, result.text

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
