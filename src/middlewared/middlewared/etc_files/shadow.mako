<%
    from middlewared.utils import filter_list
    from middlewared.utils.security import shadow_parse_aging

    sec = render_ctx['system.security.config']

    def get_passwd(entry):
        if entry['password_disabled']:
            return "*"
        elif user['locked']:
            return "!"

        return entry['unixhash']

%>\
% for user in filter_list(render_ctx['user.query'], [], {'order_by': ['-builtin', 'uid']}):
${user['username']}:${get_passwd(user)}:${shadow_parse_aging(user, sec)}
% endfor
