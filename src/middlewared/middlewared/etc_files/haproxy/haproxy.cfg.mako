<%
    devices = middleware.call_sync('vm.get_display_devices_ui_info')
%>\
global
    log /dev/log local0 emerg emerg
    chroot /var/lib/haproxy
    user haproxy
    group haproxy
    daemon

defaults
    log global
    mode	http
    option	dontlognull
    timeout connect 5000
    timeout client  50000
    timeout server  50000
    errorfile 400 /etc/haproxy/errors/400.http
    errorfile 403 /etc/haproxy/errors/403.http
    errorfile 408 /etc/haproxy/errors/408.http
    errorfile 500 /etc/haproxy/errors/500.http
    errorfile 502 /etc/haproxy/errors/502.http
    errorfile 503 /etc/haproxy/errors/503.http
    errorfile 504 /etc/haproxy/errors/504.http

frontend vms
    bind ${middleware.call_sync('vm.get_haproxy_uri')}
% for device in devices:
    acl PATH_${device['id']} path_beg -i /${device['id']}
    use_backend be_${device['id']} if PATH_${device['id']}
% endfor

% for device in devices:
backend be_${device['id']}
    server static ${device['redirect_uri']} check
    http-request replace-path /${device['id']}(.*) \1

% endfor
