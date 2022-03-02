<%
    from middlewared.utils import filter_list

    def get_passwd(entry):
        if entry['password_disabled']:
            return "*"
        elif user['locked']:
            return "!"

        return entry['unixhash']
%>\
% for user in filter_list(render_ctx['user.query'], [], {'order_by': ['-builtin', 'uid']}):
${user['username']}:${get_passwd(user)}:18397:0:99999:7:::
% endfor
