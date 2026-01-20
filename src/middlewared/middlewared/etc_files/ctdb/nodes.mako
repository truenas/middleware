<%
    # presence of the nodes file is ultimate arbiter of whether ctdb will start
    from middlewared.utils.origin import HA_HEARTBEAT_IPS
    if not render_ctx['failover.licensed']:
        raise FileShouldNotExist

%>

${'\n'.join(HA_HEARTBEAT_IPS)}
