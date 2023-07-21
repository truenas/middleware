<%
    from middlewared.utils import filter_list

    users = filter_list(render_ctx['user.query'], [], {'order_by': ['-builtin', 'uid']})
%>\
% for user in users:
${user['username']}:x:${user['uid']}:${user['group']['bsdgrp_gid']}:${user['full_name']}:${user['home']}:${user['shell']}
% endfor
% if render_ctx.get('cluster_healthy'):
% for user in filter_list(render_ctx['clustered_users'], [], {'order_by': ['uid']}):
${user['username']}:x:${user['uid']}:${user['gid']}:${user['full_name']}:/var/empty:/usr/sbin/nologin
% endfor
% endif
