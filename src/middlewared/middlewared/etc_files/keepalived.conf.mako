<%
    licensed = middleware.call_sync('failover.licensed')
    node = middleware.call_sync('failover.node')

    if licensed and node == 'MANUAL':
        middleware.logger.error(
            'Chassis position could not be determined.'
            ' Keepalived config not generated.'
        )
	raise FileShouldNotExist()

    config = middleware.call_sync('failover.config')

    advert_int = .68 # default 2 second timeout
    if config['timeout'] > 2:
        # https://tools.ietf.org/html/rfc5798#section-6.1
        # Formula is there so I solved for (y) to get advert_int
        # I round to the 100th decimal place since VRRP version 3
        # uses centisecond intervals by default
        advert_int = round(((128 * config['timeout']) / 385), 2)

    info = middleware.call_sync('interface.query')
    info = [i for i in info if len(i['failover_virtual_aliases'])]

    if not info:
        middleware.logger.error(
	    'No interfaces configured for failover.'
	    ' Keepalived config not generated.'
	)
	raise FileShouldNotExist()

%>\
global_defs {
    vrrp_notify_fifo /var/run/vrrpd.fifo
}
% for i in info:
vrrp_instance ${i['id']} {
    interface ${i['id']}
    state BACKUP
    advert_int ${advert_int}
    nopreempt
    virtual_router_id 20
    priority 254
    version 3
    unicast_peer {
    % for j in i['failover_aliases'] if node == 'A' else i['aliases']:
        ${j['address']}
    % endfor
    }
    virtual_ipaddress {
    % for j in i['failover_virtual_aliases']:
        ${j['address']}
    % endfor
    }
}
% endfor
