<%
    ftp = render_ctx['ftp.config']
    users = [user["username"] for user in render_ctx['user.query']]

    # Exclude root
    ftpusers = [user for user in users if user != 'root']
%>
${"\n".join(ftpusers) + "\n"}
