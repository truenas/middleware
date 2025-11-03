<%
    from middlewared.utils.filter_list import filter_list

    users = filter_list(render_ctx['user.query'], [], {'order_by': ['-builtin', 'uid']})
%>\
% for user in users:
${user['username']}:x:${user['uid']}:${user['group']['bsdgrp_gid']}:${user['full_name']}:${user['home']}:${user['shell']}
% endfor
