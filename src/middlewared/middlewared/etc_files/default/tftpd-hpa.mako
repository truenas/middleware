<%
    tftp = middleware.call_sync("tftp.config")

    options = ["--secure", tftp["options"]]
    if tftp["newfiles"]:
        options.append("--create")
    if tftp["umask"]:
        options.append(f"--umask {tftp['umask']}")
%>
TFTP_USERNAME="${tftp["username"]}"
TFTP_DIRECTORY="${tftp["directory"]}"
TFTP_ADDRESS="${tftp["host"]}:${tftp["port"]}"
TFTP_OPTIONS="${" ".join(options)}"
