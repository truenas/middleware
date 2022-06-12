<%
    base_name = middleware.call_sync('iscsi.global.config')['basename']
    targets = middleware.call_sync('iscsi.target.query', [['auth_networks', '!=', []]])
%>\
% for target in targets:
${base_name}:${target['name']} ALL
% endfor
