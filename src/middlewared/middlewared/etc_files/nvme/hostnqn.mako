<%
        hostnqn = middleware.call_sync('nvme.host.hostnqn')
%>\
% if hostnqn:
${hostnqn}
% endif
