<%
    licensed = middleware.call_sync('failover.licensed'):
    node = middleware.call_sync('failover.node')

    if licensed and node == 'MANUAL':
        middleware.logger.error(
            'Chassis position could not be determined.'
            ' Keepalived config not generated.'
        )

    config = middleware.call_sync('failover.config')

    advert_int = .68 # default 2 second timeout
    if config['timeout'] > 2:
        # https://tools.ietf.org/html/rfc5798#section-6.1
        # Formula is there so I solved for (y) to get advert_int
        # I round to the 100th decimal place since VRRP version 3
        # uses centisecond intervals by default
        advert_int = round(((128 * config['timeout']) / 385), 2)

    info = middleware.call_sync('datastore.query', 'network_interfaces')
%>\
% if node != 'MANUAL':
global_defs {
    vrrp_notify_fifo /var/run/vrrpd.fifo
}
    % for i in info:
vrrp_instance ${i['int_interface']} {
    state BACKUP
    advert_int % advert_int
    nopreempt
    virtual_router_id 20
    priority 254
    version 3
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
