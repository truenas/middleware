<%
    # Disallow built-in users
    disallowed_users = [user["username"] for user in render_ctx['user.query']]
%>
#
# List of users NOT allowed to login via FTP
#
${"\n".join(disallowed_users) + "\n"}
