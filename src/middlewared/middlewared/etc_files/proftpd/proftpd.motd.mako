<%
    ftp = render_ctx['ftp.config']
    if ftp["banner"]:
        banner = ftp["banner"]
    else:
        banner = "Welcome to TrueNAS FTP Server"

%>\
${banner}
