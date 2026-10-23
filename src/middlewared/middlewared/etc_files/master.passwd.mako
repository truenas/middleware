<%
    users = sorted(render_ctx['user.query'], key=lambda user: (not user.builtin, user.uid))
%>\
% for user in users:
${user.username}:x:${user.uid}:${user.group['bsdgrp_gid']}:${user.full_name}:${user.home}:${user.shell}
% endfor
