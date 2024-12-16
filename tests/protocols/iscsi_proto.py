import contextlib
import inspect
import socket

import iscsi
from functions import SRVTarget, get_host_ip
from pyscsi.pyscsi.scsi import SCSI
from pyscsi.utils import init_device


def initiator_name_supported():
    """
    Returns whether a non-None initiator name may be supplied.

    This can have an impact on what kinds of tests can be run.
    """
    return 'initiator_name' in inspect.signature(init_device).parameters


def iscsi_scsi_connect(host, iqn, lun=0, user=None, secret=None, target_user=None, target_secret=None, initiator_name=None):
    """
    Connect to the specified target, returning a SCSI object from python-scsi.

    See docs at:
    https://github.com/python-scsi/python-scsi/blob/master/pyscsi/pyscsi/scsi.py

    Basic workflow can be something like this:

    s = iscsi_scsi_connect(<ip address>, <iqn> , <lun>)
    s.testunitready()
    pprint.pprint(s.inquiry().result)
    s.device.close()
    """
    hil = f"{host}/{iqn}/{lun}"
    if user is None and secret is None:
        device_str = f"iscsi://{hil}"
    elif user and secret:
        if target_user is None and target_secret is None:
            # CHAP
            device_str = f"iscsi://{user}%{secret}@{hil}"
        elif target_user and target_secret:
            # Mutual CHAP
            device_str = f"iscsi://{user}%{secret}@{hil}?target_user={target_user}&target_password={target_secret}"
        else:
            raise ValueError("If either of target_user and target_secret is set, then both should be set.")
    else:
        raise ValueError("If either of user and secret is set, then both should be set.")
    if initiator_name:
        if not initiator_name_supported():
            raise ValueError("Initiator name supplied, but not supported.")
        device = init_device(device_str, initiator_name=initiator_name)
    else:
        device = init_device(device_str)
    s = SCSI(device)
    s.blocksize = 512
    return s


@contextlib.contextmanager
def iscsi_scsi_connection(host, iqn, lun=0, user=None, secret=None, target_user=None, target_secret=None, initiator_name=None):
    """
    Factory function to connect to the specified target, returning a SCSI
    object from python-scsi.

    See docs at:
    https://github.com/python-scsi/python-scsi/blob/master/pyscsi/pyscsi/scsi.py

    Basic workflow can be something like this:

    with iscsi_scsi_connection(<ip address>, <iqn> , <lun>) as s:
        s.testunitready()
        inqdata = s.inquiry().result
    """

    s = iscsi_scsi_connect(host, iqn, lun, user, secret, target_user, target_secret, initiator_name)

    try:
        yield s
    finally:
        s.device.close()


class ISCSIDiscover:
    def __init__(self,
                 hostname=None,
                 initiator_username=None,
                 initiator_password=None,
                 target_username=None,
                 target_password=None,
                 initiator_name=None,
                 ):
        self._hostname = hostname or get_host_ip(SRVTarget.DEFAULT)
        self._initiator_username = None
        self._initiator_password = None
        self._target_username = None
        self._target_password = None
        self._initiator_name = None

        try:
            self._ip = socket.gethostbyname(self._hostname)
        except socket.error:
            raise ValueError(f'Cannot resolve: {self._hostname}')

        if initiator_username is not None or initiator_password is not None:
            if initiator_username is None or initiator_password is None:
                raise ValueError("If supply one then must supply both: initiator_username, initiator_password")
            self._initiator_username = initiator_username
            self._initiator_password = initiator_password

        if target_username is not None or target_password is not None:
            if target_username is None or target_password is None:
                raise ValueError("If supply one then must supply both: target_username, target_password")
            self._target_username = target_username
            self._target_password = target_password

        if initiator_name:
            self._initiator_name = initiator_name
        else:
            self._initiator_name = f'iqn.2018-01.org.pyscsi:{socket.gethostname()}'

    def __enter__(self):
        return self

    def discover(self):
        connected = False
        try:
            ctx = iscsi.Context(self._initiator_name)
            ctx.set_session_type(iscsi.ISCSI_SESSION_DISCOVERY)
            ctx.set_header_digest(iscsi.ISCSI_HEADER_DIGEST_NONE)
            if self._initiator_username and self._initiator_password:
                ctx.set_initiator_username_pwd(self._initiator_username, self._initiator_password)
            if self._target_username and self._target_password:
                ctx.set_target_username_pwd(self._target_username, self._target_password)
            ctx.connect(self._ip, -1)
            connected = True
            return ctx.discover()
        except Exception:
            return {}
        finally:
            if connected:
                ctx.disconnect()

    def ip(self):
        return self._ip

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
