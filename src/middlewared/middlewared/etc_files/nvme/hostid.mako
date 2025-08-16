<%
        hostid = middleware.call_sync('nvme.host.hostid')
%>\
% if hostid:
${hostid}
% endif
