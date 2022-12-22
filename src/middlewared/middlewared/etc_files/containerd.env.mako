<%
    config = middleware.call_sync('network.configuration.config')
%>\
# Containerd Environment file
# https://github.com/k3s-io/k3s/pull/3553

% if config['httpproxy']:
CONTAINERD_HTTP_PROXY="${config['httpproxy']}"
CONTAINERD_HTTPS_PROXY="${config['httpproxy']}"
% endif
