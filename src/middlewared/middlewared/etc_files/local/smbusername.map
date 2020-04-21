#
# SMB.CONF(5)		The configuration file for the Samba suite 
#
<%
    """
    The username map is required for proper support of microsoft accounts
    that are also email addresses. See SMB.CONF(5) for more details.
    """
    users = middleware.call_sync('user.query', [
        ('microsoft_account', '=', True),
        ('email', '!=', None),
        ('email', '!=', ''),
    ])

%>
% if users:
% for user in users:
${user['username']} = ${user['email']}
% endfor
% endif
