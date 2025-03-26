<%
    from middlewared.utils import filter_list
    from middlewared.utils.security import shadow_parse_aging

    sec = render_ctx['system.security.config']
    max_age_overrides = None

    password_full_admin_users = filter_list(render_ctx['user.query'], [
        ['roles', 'rin', 'FULL_ADMIN'],
        ['password_disabled', '=', False],
        ['unixhash', '!=', '*'],
        ['locked', '=', False],
    ])

    if sec['max_password_age'] and password_full_admin_users:
        unexpired = filter_list(password_full_admin_users, [
           ['password_age', '<', sec['max_password_age'] - 1]
        ])
        if unexpired:
            middleware.call_sync('alert.oneshot_delete', 'AllAdminAccountsExpired', None)
        else:
            middleware.call_sync('alert.oneshot_create', 'AllAdminAccountsExpired', None)
            max_age_overrides = set([user['username'] for user in password_full_admin_users])

    def get_passwd(entry):
        if entry['password_disabled']:
            return "*"
        elif entry['locked']:
            return "!"

        return entry['unixhash']

%>\
% for user in filter_list(render_ctx['user.query'], [], {'order_by': ['-builtin', 'uid']}):
${user['username']}:${get_passwd(user)}:${shadow_parse_aging(user, sec, max_age_overrides)}
% endfor
