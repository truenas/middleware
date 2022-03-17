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
