<%
mapped = [
    group for group in render_ctx['group.query']
    if group.local and group.userns_idmap not in (0, None) and not group.roles
]
%>\
% for group in mapped:
% if group.userns_idmap == 'DIRECT':
0:${group.gid}:${group.gid}
% else:
0:${group.gid}:${group.userns_idmap}
% endif
% endfor
