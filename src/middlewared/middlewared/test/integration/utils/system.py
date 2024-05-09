from .ssh import ssh


def reset_systemd_svcs(svcs_to_reset):
    '''
    Systemd services can get disabled if they restart too
    many times or too quickly.   This can happen during testing.
    Input a space delimited string of systemd services to reset.
    Example usage:
        reset_systemd_svcs("nfs-idmapd nfs-mountd nfs-server rpcbind rpc-statd")
    '''
    ssh(f"systemctl reset-failed {svcs_to_reset}")
