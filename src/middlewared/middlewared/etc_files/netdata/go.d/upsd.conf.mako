<%
    ups_config = middleware.call_sync('ups.config')
    ups_uri = 'localhost'
    if ups_config['mode'] == 'SLAVE':
        ups_uri = ups_config['remotehost']
%>\
jobs:
  - name: local
    address: ${ups_uri}:${ups_config['remoteport']}
%if ups_config['mode'] == 'SLAVE':
    username: ${ups_config['monuser']}
    password: ${ups_config['monpwd']}
%endif
