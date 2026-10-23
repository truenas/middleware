<%
mapped = [
    user for user in render_ctx['user.query']
    if user.local and user.userns_idmap not in (0, None) and not user.roles
]
%>\
% for user in mapped:
% if user.userns_idmap == 'DIRECT':
0:${user.uid}:${user.uid}
% else:
0:${user.uid}:${user.userns_idmap}
% endif
% endfor
