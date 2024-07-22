<%
    # Disallow built-in users
    ftp = render_ctx['ftp.config']
    disallowed_users = [user["username"] for user in render_ctx['user.query']]
%>
#
# List of users NOT allowed to login via FTP
#
${"\n".join(disallowed_users) + "\n"}
