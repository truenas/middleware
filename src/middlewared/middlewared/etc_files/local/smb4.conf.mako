#
# SMB.CONF(5)		The configuration file for the Samba suite 
#
<%
    smb_ha_mode = middleware.call_sync('smb.get_smb_ha_mode')
    failover_status = middleware.call_sync('failover.status')
%>

[global]
    rpc_daemon:mdssd = disabled
    rpc_server:mdssvc = disabled
    % if failover_status in ('SINGLE', 'MASTER'):
    % if smb_ha_mode == "CLUSTERED":
    clustering = Yes
    ctdb:registry.tdb = Yes
    kernel share modes = No
    include = registry
    % else:
    clustering = No
    include = registry
    % endif
    % else:
    clustering = No
    netbiosname = TN_STANDBY
    % endif
