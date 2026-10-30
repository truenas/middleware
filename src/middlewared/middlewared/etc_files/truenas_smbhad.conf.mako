<%
    if not render_ctx['failover.licensed']:
        raise FileShouldNotExist

    node = render_ctx['failover.node']
    if node not in ('A', 'B'):
        raise FileShouldNotExist

    # The addresses on the internal link, as failover.local_ip and failover.remote_ip
    # report them. They are written out because the daemon cannot detect them itself:
    # with net.ipv4.ip_nonlocal_bind on, both heartbeat addresses bind on either node.
    local_address, peer_address = {
        'A': ('169.254.10.1', '169.254.10.2'),
        'B': ('169.254.10.2', '169.254.10.1'),
    }[node]
%>\
[smbhad]
node = ${node}
local_address = ${local_address}
peer_address = ${peer_address}
