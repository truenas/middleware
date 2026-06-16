from middlewared.utils.network_.procfs import InetInfoEntry, read_proc_net


def connection_count() -> int:
    """Return the number of active connections"""
    # FTP listening port is 21
    ftp = 21

    try:
        proc_data = read_proc_net()
    except Exception:
        return 0

    if isinstance(proc_data, InetInfoEntry):
        proc_data = [proc_data]

    # NOTE: This count includes multiple 'connections' from a single client.
    return sum(1 for x in proc_data if x.local_port == ftp and x.remote_port != 0)
