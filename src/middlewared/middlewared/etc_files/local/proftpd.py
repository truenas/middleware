import os

from middlewared.utils import osc


def setup(middleware):
    ftp = middleware.call_sync("ftp.config")

    os.makedirs("/var/log/proftpd", exist_ok=True)
    os.makedirs("/var/run/proftpd", exist_ok=True)

    open("/var/run/proftpd/proftpd.delay", "w+").close()
    open("/etc/hosts.allow", "w+").close()
    open("/etc/hosts.deny", "w+").close()

    if osc.IS_LINUX:
        filters = [["builtin", "=", True], ["username", "!=", "ftp"]]
        if ftp["rootlogin"]:
            filters.append(["username", "!=", "root"])

        ftpusers = [user["username"] for user in middleware.call_sync("user.query", filters)]

        with open("/etc/ftpusers", "w") as f:
            f.write("\n".join(ftpusers) + "\n")

    open("/var/log/wtmp", "w+").close()
    os.chmod("/var/log/wtmp", 0o644)

    with open("/var/run/proftpd/proftpd.motd", "w") as f:
        if ftp["banner"]:
            f.write(ftp["banner"] + "\n")
        else:
            product_name = middleware.call_sync("system.product_name")
            f.write(f"Welcome to {product_name} FTP Server\n")


def render(service, middleware):
    setup(middleware)
