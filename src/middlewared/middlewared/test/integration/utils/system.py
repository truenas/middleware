import os
import sys
from .ssh import ssh
from middlewared.test.integration.utils import truenas_server

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import ha
except ImportError:
    ha = False

__all__ = ["reset_systemd_svcs", "restart_systemd_svc", "get_gssproxy_state"]


def reset_systemd_svcs(svcs_to_reset):
    '''
    Systemd services can get disabled if they restart too
    many times or too quickly.   This can happen during testing.
    Input a space delimited string of systemd services to reset.
    Example usage:
        reset_systemd_svcs("nfs-idmapd nfs-mountd nfs-server rpcbind rpc-statd")
    '''
    ssh(f"systemctl reset-failed {svcs_to_reset}")


def restart_systemd_svc(svc_to_restart: str, remote_node: bool = False):
    '''
    --- CI testing function ---
    Command a service restart via systemctl.
    Optional to request command on remote node (HA only)
    NOTE: May be unstable with calls to standby node.
    '''
    assert ssh(f"systemctl status {svc_to_restart}")
    node_ip = None
    if remote_node:
        assert ha is True, "Cannot select remote_node on non-HA system"
        ha_ips = truenas_server.ha_ips()
        node_ip = ha_ips['standby']

    assert ssh(f"systemctl restart {svc_to_restart}", ip=node_ip), \
        (ssh(f"systemctl status {svc_to_restart}", ip=node_ip), ssh(f"journalctl -xeu {svc_to_restart} | tail -100", ip=node_ip))


def get_gssproxy_state() -> int | None:
    """
    Return value of /proc/net/rpc/use-gss-proxy or
    None if proc file does not exist or read failure
    """
    GSSPROXY_PROCFILE = '/proc/net/rpc/use-gss-proxy'
    rv = None
    try:
        val = ssh(f"cat {GSSPROXY_PROCFILE}")
        rv = int(val)
    except Exception:
        pass

    return rv
