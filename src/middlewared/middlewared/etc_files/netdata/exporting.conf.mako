<%
    from middlewared.utils.filter_list import filter_list
    graphite_confs = filter_list(middleware.call_sync('reporting.exporters.query'), [['attributes.exporter_type', '=', 'GRAPHITE']])
%>\
% for graphite_conf in graphite_confs:
[${graphite_conf['attributes']['exporter_type'].lower()}:${graphite_conf['name']}]
    enabled = ${"yes" if graphite_conf['enabled'] else "no"}
    destination = ${graphite_conf['attributes']['destination_ip']}:${graphite_conf['attributes']['destination_port']}
    prefix = ${graphite_conf['attributes']['prefix']}
    hostname = ${graphite_conf['attributes']['namespace']}
    send configured labels = no
    update every = ${graphite_conf['attributes']['update_every']}
    buffer on failures = ${graphite_conf['attributes']['buffer_on_failures']}
    send names instead of ids = ${"yes" if graphite_conf['attributes']['send_names_instead_of_ids'] else "no"}
    send charts matching = ${graphite_conf['attributes']['matching_charts']}
% endfor
