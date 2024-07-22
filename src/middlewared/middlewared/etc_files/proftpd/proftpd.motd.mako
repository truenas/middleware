<%
    ftp = render_ctx['ftp.config']
    if ftp["banner"]:
        banner = ftp["banner"] + "\n"
    else:
        banner = "Welcome to TrueNAS FTP Server\n"

%>
${banner}
