<%
    from middlewared.alert.source.security import AllAdminAccountsExpiredAlert
    from middlewared.utils.security import shadow_parse_aging

    sec = render_ctx['system.security.config']
    max_age_overrides = None
    root_always_enabled = False

    users = render_ctx['user.query']

    password_full_admin_users = [
        user for user in users
        if 'FULL_ADMIN' in user.roles
        and not user.password_disabled
        and user.unixhash.get_secret_value() != '*'
        and not user.locked
    ]

    if next(user for user in users if user.username == 'root').password_disabled:
        # The following provides way for root user to avoid getting locked out
        # of webui via due to PAM enforcing password policies on the root
        # account. Specifically, some legacy users have configured the root
        # account so its password has password_disabled = true.
        root_always_enabled = middleware.call_sync2(middleware.services.privilege.always_has_root_password_enabled)

    if sec.max_password_age and password_full_admin_users:
        unexpired = [
            user for user in password_full_admin_users
            if user.password_age is not None and user.password_age < sec.max_password_age - 1
        ]
        if unexpired:
            middleware.call_sync2(middleware.services.alert.oneshot_delete, 'AllAdminAccountsExpired', None)
        else:
            middleware.call_sync2(middleware.services.alert.oneshot_create, AllAdminAccountsExpiredAlert())
            max_age_overrides = set([user.username for user in password_full_admin_users])

    def get_passwd(entry):
        if entry.username == 'root' and root_always_enabled:
            return entry.unixhash.get_secret_value()
        if entry.password_disabled:
            return "*"
        elif entry.locked:
            return "!"

        return entry.unixhash.get_secret_value()

%>\
% for user in sorted(users, key=lambda user: (not user.builtin, user.uid)):
${user.username}:${get_passwd(user)}:${shadow_parse_aging(user, sec, max_age_overrides)}
% endfor
