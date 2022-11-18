import contextlib

from .smb_proto import SMB
from .nfs_proto import SSH_NFS


@contextlib.contextmanager
def smb_connection(**kwargs):
    c = SMB()
    c.connect(**kwargs)

    try:
        yield c
    finally:
        c.disconnect()
