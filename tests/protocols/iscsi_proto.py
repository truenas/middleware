import contextlib
import inspect

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
