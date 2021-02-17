<%
    users_map = {
        i['id']: i
        for i in middleware.call_sync('user.query')
    }

    def get_usernames(group):
        return ','.join([
            users_map[i]['username']
            for i in group['users']
            if i in users_map and users_map[i]['group']['id'] != group['id']
        ])

    if IS_FREEBSD:
        no_password = '*'
    else:
        no_password = 'x'
%>\
% for group in middleware.call_sync('group.query', [], {'order_by': ['-builtin', 'gid']}):
${group['group']}:${no_password}:${group['gid']}:${get_usernames(group)}
% endfor
% if IS_FREEBSD and middleware.call_sync('nis.config')['enable']:
+:${no_password}::\
% endif
