import contextlib
import ssl
from ftplib import FTP, FTP_TLS

# See docs at:
# https://docs.python.org/3/library/ftplib.html


def ftp_connect(host, port=0):
    """
    Connect to the specified host, returning an FTP object from ftplib.
    """
    ftp = FTP(host, port)
    return ftp


def ftps_connect(host, ctx=None):
    """
    Connect to the specified host, returning an FTP_TLS object from ftplib.
    Use a simple TLS setup.
    """
    if ctx is None:
        ctx = ssl._create_unverified_context()
    ftps = FTP_TLS(host, context=ctx)
    ftps.auth()
    ftps.prot_p()
    return ftps


@contextlib.contextmanager
def ftp_connection(host, port=0):
    """
    Factory function to connect to the specified host
    RETURN: FTP object from ftplib.

    EXAMPLE USAGE:
    with ftp_connection(<hostname | ip address>) as ftp:
        ftp.login()
        print(ftp.mlsd())
    """
    ftp = ftp_connect(host, port=0)
    try:
        yield ftp
    finally:
        ftp.close()


@contextlib.contextmanager
def ftps_connection(host, ctx=None):
    """
    Factory function to connect to the specified host
    The TLS connection does not allow port selection
    RETURN: FTP_TLS object from ftplib.

    EXAMPLE USAGE:
    with ftps_connection(<hostname | ip address>) as ftps:
        ftp.login()
        print(ftps.mlsd())
    """
    ftps = ftps_connect(host, ctx)
    try:
        yield ftps
    finally:
        ftps.close()
