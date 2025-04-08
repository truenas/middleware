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

__all__ = ["reset_systemd_svcs", "restart_systemd_svc"]


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
    '''
    assert ssh(f"systemctl status {svc_to_restart}")
    node_ip = None
    if remote_node:
        assert ha is True, "Cannot select remote_node on non-HA system"
        ha_ips = truenas_server.ha_ips()
        node_ip = ha_ips['standby']

    ssh(f"systemctl restart {svc_to_restart}", ip=node_ip)
