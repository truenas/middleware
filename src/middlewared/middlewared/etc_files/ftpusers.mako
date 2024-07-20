<%
    ftp = render_ctx['ftp.config']
    users = [user["username"] for user in render_ctx['user.query']]

    exclude = []
    if ftp["rootlogin"]:
        exclude.append('root')

    ftpusers = [user for user in users if user not in exclude]
%>
${"\n".join(ftpusers) + "\n"}
