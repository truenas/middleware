#
# SMB.CONF(5)		The configuration file for the Samba suite 
#
<%
    from middlewared.utils import filter_list

    """
    The username map is required for proper support of microsoft accounts
    that are also email addresses. See SMB.CONF(5) for more details.
    """
    users = filter_list(render_ctx['user.query'], [
        ('microsoft_account', '=', True),
        ('email', '!=', None),
        ('email', '!=', ''),
    ])
    if not users:
        raise FileShouldNotExist()

%>
% for user in users:
${user['username']} = ${user['email']}
% endfor
