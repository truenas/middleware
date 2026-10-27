<%
    if not render_ctx['failover.licensed']:
        raise FileShouldNotExist

    node = render_ctx['failover.node']
    if node not in ('A', 'B'):
        raise FileShouldNotExist
%>\
[smbhad]
node = ${node}
