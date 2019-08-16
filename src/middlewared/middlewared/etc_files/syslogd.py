from datetime import datetime
import logging
import os
import shlex
import shutil
import subprocess
import textwrap

logger = logging.getLogger(__name__)


def generate_syslog_remote_destination(middleware, advanced_config):
    result = ""
    if advanced_config["syslogserver"]:
        if ":" in advanced_config["syslogserver"]:
            host, port = advanced_config["syslogserver"].rsplit(":", 1)
        else:
            host, port = advanced_config["syslogserver"], "514"

        result += 'destination loghost { '

        if advanced_config["syslog_transport"] == "TLS":
            try:
                certificate = middleware.call_sync(
                    "certificate.query",
                    [
                        ("id", "=", advanced_config["syslog_tls_certificate"]),
                        ("revoked", "=", False),
                    ],
                    {"get": True}
                )
            except IndexError:
                logger.warning("Syslog TLS certificate not available, skipping remote syslog destination")
                return ""

            try:
                ca_dir = "/etc/certificates"
                for filename in os.listdir(ca_dir):
                    if filename.endswith(".0") and os.path.islink(os.path.join(ca_dir, filename)):
                        os.unlink(os.path.join(ca_dir, filename))
                os.symlink(certificate["certificate_path"],
                           os.path.join(ca_dir, "%x.0" % certificate["subject_name_hash"]))
            except Exception:
                logger.error("Error symlinking syslog certificate, skipping remote syslog destination", exc_info=True)
                return ""

            result += f'syslog("{host}" port({port}) transport("tls") tls(ca-dir("{ca_dir}")));'
        else:
            transport = advanced_config["syslog_transport"].lower()
            result += f'{transport}("{host}" port({port}) localport(514));'

        result += ' };\n'
        result += f'log {{ source(src); filter({advanced_config["sysloglevel"].lower()});'
        result += f'destination(loghost); }};\n'

    return result


def generate_syslog_conf(middleware):
    # In 12.0 we can have /conf/base/usr__local__etc as the base point for /usr/local/etc/tmpfs
    # (see commit 704f1eb60f438171690d79bfdf17e95044cc6bb2)
    if os.path.isdir("/conf/base/usr__local__etc"):
        shutil.copy("/conf/base/usr__local__etc/syslog-ng.conf.freenas",
                    "/etc/local/syslog-ng.conf")
    else:
        shutil.copy("/conf/base/etc/local/syslog-ng.conf.freenas",
                    "/etc/local/syslog-ng.conf")

    with open("/etc/local/syslog-ng.conf") as f:
        syslog_conf = f.read()

    advanced_config = middleware.call_sync("system.advanced.config")

    if advanced_config["fqdn_syslog"]:
        syslog_conf = syslog_conf.replace("use-fqdn(no)", "use-fqdn(yes)")

    syslog_conf += generate_syslog_remote_destination(middleware, advanced_config)

    with open("/etc/local/syslog-ng.conf", "w") as f:
        f.write(syslog_conf)


def generate_ha_syslog(middleware):
    if middleware.call_sync("system.is_freenas"):
        return

    if not middleware.call_sync("failover.licensed"):
        return

    node = middleware.call_sync("failover.node")
    if node == "MANUAL":
        return

    controller_port = 7777
    if node == "A":
        controller_ip = "169.254.10.1"
        controller_other_ip = "169.254.10.2"
        controller_file = "/root/syslog/controller_b"
    else:
        controller_ip = "169.254.10.2"
        controller_other_ip = "169.254.10.1"
        controller_file = "/root/syslog/controller_a"

    os.makedirs("/root/syslog", mode=0o755, exist_ok=True)

    with open("/etc/local/syslog-ng.conf") as f:
        syslog_conf = f.read()

    syslog_conf += textwrap.dedent(f"""\
        source this_controller {{
            udp(ip({controller_ip}) port({controller_port}));
            udp(default-facility(syslog) default-priority(emerg));
        }};

        log {{
            source(this_controller);
            destination(other_controller_file);
        }};

        destination other_controller_file {{ file("{controller_file}"); }};
        destination other_controller {{ udp("{controller_other_ip}" port({controller_port})); }};

        log {{ source(src); filter(f_not_mdnsresponder); filter(f_not_nginx); destination(other_controller); }};
    """)

    with open("/etc/local/syslog-ng.conf", "w") as f:
        f.write(syslog_conf)

    # Be sure and copy fresh file since we're appending
    shutil.copy("/conf/base/etc/newsyslog.conf.template", "/etc/newsyslog.conf")

    with open("/etc/newsyslog.conf") as f:
        newsyslog_conf = f.read()

    newsyslog_conf += f"{controller_file}		640  10	   200	@0101T JC"

    with open("/etc/newsyslog.conf", "w") as f:
        f.write(newsyslog_conf)


def use_syslog_dataset(middleware):
    systemdataset = middleware.call_sync("systemdataset.config")

    if systemdataset["syslog"]:
        if middleware.call_sync("system.is_freenas"):
            return True
        else:
            return middleware.call_sync("failover.status") != "BACKUP"
    else:
        return False


def configure_syslog(middleware):
    systemdataset = middleware.call_sync("systemdataset.config")

    if not systemdataset["path"] or not use_syslog_dataset(middleware):
        if os.path.islink("/var/log"):
            if not os.path.realpath("/var/log"):
                os.rename("/var/log", "/var/log." + datetime.now().strftime("%Y%m%d%H%M%S"))
            else:
                os.unlink("/var/log")

            shutil.copytree("/conf/base/var/log", "/var/log")

        middleware.call_sync("core.reconfigure_logging")

        return

    log_path = os.path.join(systemdataset["path"], f"syslog-{systemdataset['uuid']}")
    if os.path.exists(os.path.join(log_path, "log")):
        # log directory exists, pick up any new files or
        # directories and create them. Existing files will be
        # appended. This is done this way so that ownership and
        # permissions are always preserved.

        if not os.path.islink("/var/log"):
            for item in os.listdir("/var/log"):
                dst = os.path.join(log_path, "log", item)
                item = os.path.join("/var/log", item)

                if os.path.isdir(item):
                    # Pick up any new directories and sync them
                    if not os.path.isdir(dst):
                        shutil.copytree(item, dst)
                else:
                    # If the file exists already, append to
                    # it, otherwise, copy it over.
                    if os.path.isfile(dst):
                        with open(item, "rb") as f1:
                            with open(dst, "ab") as f2:
                                shutil.copyfileobj(f1, f2)
                    else:
                        shutil.copy(item, dst)
    else:
        # This is the first time syslog is going to log to this
        # directory, so create the log directory and sync files.
        shutil.copytree("/conf/base/var/log", os.path.join(log_path, "log"))
        os.chmod(os.path.join(log_path, "log"), 0o755)
        os.chown(os.path.join(log_path, "log"), 0, 0)
        subprocess.run(f"/usr/local/bin/rsync -avz /var/log/* {shlex.quote(log_path + '/log/')}", shell=True,
                       stdout=subprocess.DEVNULL)

    if not os.path.islink("/var/log") or not os.path.realpath("/var/log"):
        os.rename("/var/log", "/var/log." + datetime.now().strftime("%Y%m%d%H%M%S"))
        os.symlink(os.path.join(log_path, "log"), "/var/log")

    # Let's make sure that the permissions for directories/files in /var/log
    # reflect that of /conf/base/var/log
    subprocess.run("mtree -c -p /conf/base/var/log | mtree -eu", cwd="/var/log", shell=True, stdout=subprocess.DEVNULL)

    middleware.call_sync("core.reconfigure_logging")


def render(service, middleware):
    generate_syslog_conf(middleware)
    generate_ha_syslog(middleware)
    configure_syslog(middleware)
