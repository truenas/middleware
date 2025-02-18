# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

class AllZpoolsFailedToImport(Exception):
    """
    This is raised if all zpools failed to
    import when becoming master.
    """
    pass


class IgnoreFailoverEvent(Exception):
    """
    This is raised when a failover event is ignored.
    """
    pass


class FencedError(Exception):
    """
    This is raised if fenced fails to run.
    """
    pass
