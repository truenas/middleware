import contextlib                                                                                                                                               
import pyscsi
from pyscsi.utils import init_device
from pyscsi.pyscsi.scsi import SCSI

def iscsi_scsi_connect(host, iqn, lun=0, user=None, secret=None, target_user=None, target_secret=None):
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
    if user is None and secret is None:
        device = init_device("iscsi://{}/{}/{}".format(host, iqn, lun))
    elif user and secret:
        if target_user is None and target_secret is None:
            # CHAP
            device = init_device("iscsi://{}%{}@{}/{}/{}".format(user, secret, host, iqn, lun))
        elif target_user and target_secret:
            # Mutual CHAP
            device = init_device("iscsi://{}%{}@{}/{}/{}?target_user={}&target_password={}".format(user, secret, host, iqn, lun, target_user, target_secret))
        else:
            raise ValueError("If either of target_user and target_secret is set, then both should be set.")
    else:
        raise ValueError("If either of user and secret is set, then both should be set.")
    s = SCSI(device)
    return s

@contextlib.contextmanager
def iscsi_scsi_connection(host, iqn, lun=0, user=None, secret=None, target_user=None, target_secret=None):
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

    s = iscsi_scsi_connect(host, iqn, lun, user, secret, target_user, target_secret)

    try:
        yield s
    finally:
        s.device.close()

