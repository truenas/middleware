#
# SMB.CONF(5)		The configuration file for the Samba suite 
#
<%
    failover_status = middleware.call_sync('failover.status')
%>

[global]
    rpc_daemon:mdssd = disabled
    rpc_server:mdssvc = disabled
    % if failover_status in ('SINGLE', 'MASTER'):
    clustering = No
    include = registry
    % else:
    clustering = No
    netbiosname = TN_STANDBY
    % endif
