import contextlib
import os
import sys

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from protocols.smb_proto import SMB, security
except ImportError:
    SMB = None
    security = None

from .client import truenas_server

__all__ = ["smb_connection"]


@contextlib.contextmanager
def smb_connection(
    host=None,
    share=None,
    encryption='DEFAULT',
    username=None,
    domain=None,
    password=None,
    smb1=False
):
    s = SMB()
    s.connect(
        host=host or truenas_server.ip,
        share=share,
        encryption=encryption,
        username=username,
        domain=domain,
        password=password,
        smb1=smb1
    )

    try:
        yield s
    finally:
        s.disconnect()
