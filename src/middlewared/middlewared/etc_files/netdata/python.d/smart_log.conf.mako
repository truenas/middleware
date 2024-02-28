<%
    smart_config_interval = middleware.call_sync('smart.config')['interval']
%>\
debian:
  name: smart
  log_path: '/var/lib/smartmontools/'
  age: ${smart_config_interval}
