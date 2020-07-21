<%
    licensed = middleware.call_sync('failover.licensed'):
    node = middleware.call_sync('failover.node')

    if licensed and node == 'MANUAL':
        middleware.logger.error(
            'Chassis position could not be determined.'
            ' Keepalived config not generated.'
        )

    info = middleware.call_sync('datastore.query', 'network_interfaces')
%>\
% if node != 'MANUAL':
    % for i in info:
vrrp_instance ${i['int_interface']} {
    # track_interface {
        # FIXME
    # }
    state BACKUP
    advert_int 1
    nopreempt
    virtual_router_id 20
    priority 100 # figure best way to do this (track_interface weight?)
    version 3
    authentication {
        auth_type PASS
        auth_pass ${i['int_pass']}
    }
    % if node == 'A':
    unicast_src_ip ${i['int_ipv4address']}
    unicast_peer {
        ${i['int_ipv4address_b']}
    }
    % elif node == 'B':
    unicast_src_ip ${i['int_ipv4address_b']}
    unicast_peer {
        ${i['int_ipv4address']}
    }
    % endif
    virtual_address {
        ${i['int_vip']} dev ${i['int_interface']}
    }
    % endfor
}
% endif
