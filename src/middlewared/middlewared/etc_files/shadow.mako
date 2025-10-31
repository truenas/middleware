<%
    from middlewared.utils.filter_list import filter_list
    from middlewared.utils.security import shadow_parse_aging

    sec = render_ctx['system.security.config']
    max_age_overrides = None
    root_always_enabled = False

    password_full_admin_users = filter_list(render_ctx['user.query'], [
        ['roles', 'rin', 'FULL_ADMIN'],
        ['password_disabled', '=', False],
        ['unixhash', '!=', '*'],
        ['locked', '=', False],
    ])

    if filter_list(render_ctx['user.query'], [['username', '=', 'root']], {'get': True})['password_disabled']:
        # The following provides way for root user to avoid getting locked out
        # of webui via due to PAM enforcing password policies on the root
        # account. Specifically, some legacy users have configured the root
        # account so its password has password_disabled = true.
        root_always_enabled = middleware.call_sync('privilege.always_has_root_password_enabled')

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
        if entry['username'] == 'root' and root_always_enabled:
            return entry['unixhash']
        if entry['password_disabled']:
            return "*"
        elif entry['locked']:
            return "!"

        return entry['unixhash']

%>\
% for user in filter_list(render_ctx['user.query'], [], {'order_by': ['-builtin', 'uid']}):
${user['username']}:${get_passwd(user)}:${shadow_parse_aging(user, sec, max_age_overrides)}
% endfor
