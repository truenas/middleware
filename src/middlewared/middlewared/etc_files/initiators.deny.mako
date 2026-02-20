<%
    base_name = render_ctx['iscsi.global.config']['basename']
    targets = render_ctx['iscsi.target.query']
%>\
% for target in targets:
${base_name}:${target['name']} ALL
% endfor
