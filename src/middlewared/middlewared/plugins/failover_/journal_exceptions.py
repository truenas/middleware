# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

class UnableToDetermineOSVersion(Exception):
    """
    Raised in JournalSync thread when we're unable
    to detect the remote node's OS version.
    (i.e. if remote node goes down (upgrade/reboot, etc)
    """
    pass


class OSVersionMismatch(Exception):
    """
    Raised in JournalSync thread when the remote nodes OS version
    does not match the local nodes OS version.
    """
    pass
