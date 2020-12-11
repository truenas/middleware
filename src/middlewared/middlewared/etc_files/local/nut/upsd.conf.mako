<%
    ups_config = middleware.call_sync('ups.config')
%>\
% if ups_config['rmonitor']:
LISTEN 0.0.0.0 ${ups_config['remoteport']}
LISTEN ::0 ${ups_config['remoteport']}
% else:
LISTEN 127.0.0.1 ${ups_config['remoteport']}
LISTEN ::1 ${ups_config['remoteport']}
% endif
${ups_config['optionsupsd']}
