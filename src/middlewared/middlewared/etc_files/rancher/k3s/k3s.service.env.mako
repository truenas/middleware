<%
    config = middleware.call_sync('kubernetes.config')
%>\
K3S_EXEC_OPTIONS="--cluster-cidr=${config['cluster_cidr']} --service-cidr=${config['service_cidr']} --cluster-dns=${config['cluster_dns_ip']}"
