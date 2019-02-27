import os


def setup(middleware):
    os.makedirs("/var/log/proftpd", exist_ok=True)
    os.makedirs("/var/run/proftpd", exist_ok=True)

    open("/var/run/proftpd/proftpd.delay", "w+").close()
    open("/etc/hosts.allow", "w+").close()
    open("/etc/hosts.deny", "w+").close()

    open("/var/log/wtmp", "w+").close()
    os.chmod("/var/log/wtmp", 0o644)

    ftp = middleware.call_sync("ftp.config")
    with open("/var/run/proftpd/proftpd.motd", "w") as f:
        if ftp["banner"]:
            f.write(ftp["banner"] + "\n")
        else:
            product_name = middleware.call_sync("system.product_name")
            f.write(f"Welcome to {product_name} FTP Server\n")


def render(service, middleware):
    setup(middleware)
