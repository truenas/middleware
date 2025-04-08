import contextlib
import os
import sys
from middlewared.test.integration.utils import ssh, truenas_server, restart_systemd_svc

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import ha
except ImportError:
    ha = False


@contextlib.contextmanager
def standby_syslog_to_remote_syslog(remote_log_path="/var/log/remote_log.txt"):
    '''
    Temporarily convert the syslog server on the standby node
    to a remote syslog server.  HA systems only.
    NOTE: Any operation that involves restarting or reloading syslog-ng may
          break the remote syslog configuration.
    '''
    assert ha is True, "Remote log config is available on HA systems only."

    remote_syslog_config = (
        '@version: 3.38\n'
        '@include "scl.conf"\n'
        'options { time-reap(30); mark-freq(10); keep-hostname(yes); };\n'
        '\n'
        'source s_remote_non_tls {\n'
        '    syslog ( ip-protocol(6) transport("tcp") port(514) );\n'
        '};\n'
        '\n'
        'destination d_logs {\n'
        f'    file( "{remote_log_path}"  owner("root")  group("root")  perm(0777) );\n'
        '};\n'
        '\n'
        'log {\n'
        '    source(s_remote_non_tls);\n'
        '    destination(d_logs);\n'
        '};\n'
    )
    remote_ip = truenas_server.ha_ips()['standby']
    restore_syslog_config = "ORIG_syslog-ng.config_ORIG"
    try:
        ssh(f"cp /etc/syslog-ng/syslog-ng.conf /etc/syslog-ng/{restore_syslog_config}", ip=remote_ip)
        ssh(f"echo {remote_syslog_config} > etc/syslog-ng/syslog-ng.conf", ip=remote_ip)
        restart_systemd_svc("syslog-ng", remote_node=True)
        yield remote_log_path
    finally:
        if ssh("ls /etc/syslog-ng/{restore_syslog_config}", ip=remote_ip):
            ssh(f"mv /etc/syslog-ng/{restore_syslog_config} /etc/syslog-ng/syslog-ng.conf", ip=remote_ip)
        restart_systemd_svc("syslog-ng", remote_node=True)
