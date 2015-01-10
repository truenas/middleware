% for host in dispatcher.call_sync("network.hosts.query"):
    ${host["address"]} ${" ".join(host["names"])}
% endfor