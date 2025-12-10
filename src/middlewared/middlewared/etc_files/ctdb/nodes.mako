<%
    # presence of the nodes file is ultimate arbiter of whether ctdb will start
    from middlewared.utils.origin import HA_HEARTBEAT_IPS
    if render_ctx['failover.status'] == 'SINGLE':
        raise FileShouldNotExist

    if not render_ctx['smb.config']['stateful_failover']:
        raise FileShouldNotExist
%>

${'\n'.join(HA_HEARTBEAT_IPS)}
