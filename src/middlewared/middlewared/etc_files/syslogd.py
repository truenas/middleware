from datetime import datetime
import logging
import os
import re
import shlex
import shutil
import subprocess
import textwrap


logger = logging.getLogger(__name__)

SYSLOG_NG_CONF_ORIG = "/conf/base/etc/syslog-ng/syslog-ng.conf"
SYSLOG_NG_CONF = "/etc/syslog-ng/syslog-ng.conf"
LOG_FILTER_PREFIX = "f_freebsd_"
LOG_SOURCE = "s_src"
RE_DESTINATION = re.compile(r'(#+\n# Destinations\n#+)')
RE_K3S_FILTER = re.compile(r'(\s{\s)')


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
                certificate_authority = middleware.call_sync(
                    "certificateauthority.query", [
                        ("id", "=", advanced_config["syslog_tls_certificate_authority"]), ("revoked", "=", False),
                    ],
                    {"get": True}
                )
            except IndexError:
                logger.warning("Syslog TLS certificate not available, skipping remote syslog destination")
                return ""

            result += f"syslog(\"{host}\" port({port}) transport(\"tls\") "
            try:
                ca_dir = "/etc/certificates/CA"
                for filename in os.listdir(ca_dir):
                    if filename.endswith(".0") and os.path.islink(os.path.join(ca_dir, filename)):
                        os.unlink(os.path.join(ca_dir, filename))
                os.symlink(
                    certificate_authority["certificate_path"], os.path.join(
                        ca_dir, "%x.0" % certificate_authority["subject_name_hash"]
                    )
                )
            except Exception:
                logger.error("Error symlinking syslog CA, skipping remote syslog destination", exc_info=True)
                return ""
            else:
                result += f"tls(ca-dir(\"{ca_dir}\") "

            certificate = middleware.call_sync(
                "certificate.query", [("id", "=", advanced_config["syslog_tls_certificate"])]
            )
            if certificate and not certificate[0]["revoked"]:
                result += f"key-file(\"{certificate[0]['privatekey_path']}\") " \
                          f"cert-file(\"{certificate[0]['certificate_path']}\")"
            else:
                msg = 'Skipping setting key-file/cert-file for remote syslog as '
                if not certificate:
                    msg += 'no certificate configured'
                else:
                    msg += 'specified certificate has been revoked'
                logger.debug(msg)

            result += "));"
        else:
            transport = advanced_config["syslog_transport"].lower()
            result += f'{transport}("{host}" port({port}) localport(514));'

        result += ' };\n'
        result += f'log {{ source({LOG_SOURCE}); filter({LOG_FILTER_PREFIX}{advanced_config["sysloglevel"].lower()});'
        result += f'destination(loghost); }};\n'

    return result


def generate_svc_filters():
    return textwrap.dedent("""
        #####################
        # filter k3s messages
        #####################
        filter f_k3s { program("k3s");; };
        destination d_k3s { file("/var/log/k3s_daemon.log"); };
        log { source(s_src); filter(f_k3s); destination(d_k3s); };

        #####################
        # filter docker/containerd messages
        #####################
        filter f_containerd { program("containerd") or program("dockerd"); };
        destination d_containerd { file("/var/log/containerd.log"); };
        log { source(s_src); filter(f_containerd); destination(d_containerd); };

        #####################
        # filter kube-router messages
        #####################
        filter f_kube_router { program("kube-router"); };
        destination d_kube_router { file("/var/log/kube_router.log"); };
        log { source(s_src); filter(f_kube_router); destination(d_kube_router); };

        #####################
        # filter haproxy messages
        #####################
        filter f_haproxy { program("haproxy");; };
        destination d_haproxy { file("/var/log/haproxy.log"); };
        log { source(s_src); filter(f_haproxy); filter(f_crit); destination(d_haproxy); };
    """)


def generate_syslog_conf(middleware):
    with open(SYSLOG_NG_CONF_ORIG) as f:
        syslog_conf = RE_DESTINATION.sub(fr"{generate_svc_filters()}\n\1", f.read())

    for line in (
        "filter f_daemon { facility(daemon) and not filter(f_debug); };",
        "filter f_syslog3 { not facility(auth, authpriv, mail) and not filter(f_debug); };",
        "filter f_messages { level(info,notice,warn) and"
    ):
        syslog_conf = syslog_conf.replace(
            line, RE_K3S_FILTER.sub(
                r'\1not filter(f_k3s) and not filter(f_containerd) and not filter(f_haproxy)'
                r' and not filter(f_kube_router) and ',
                line
            )
        )

    advanced_config = middleware.call_sync("system.advanced.config")
    if advanced_config["fqdn_syslog"]:
        syslog_conf = syslog_conf.replace("use-fqdn(no)", "use-fqdn(yes)")
        syslog_conf = syslog_conf.replace("use_fqdn(no)", "use_fqdn(yes)")

    syslog_conf += generate_syslog_remote_destination(middleware, advanced_config)

    with open(SYSLOG_NG_CONF, "w") as f:
        f.write(syslog_conf)


def generate_ha_syslog(middleware):
    if not middleware.call_sync("system.is_enterprise"):
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

    with open(SYSLOG_NG_CONF) as f:
        syslog_conf = f.read()

    syslog_conf += textwrap.dedent(f"""\


        #
        # filter smbd related messages across HA syslog connection
        #
        filter f_not_smb {{ not program("smbd"); }};


        #
        # syslog-ng TrueNAS HA configuration
        #
        source this_controller {{
            network(
                localip("{controller_ip}")
                port({controller_port})
                transport("udp")
                default-facility(syslog)
                default-priority(emerg)
            );
        }};

        log {{
            source(this_controller);
            destination(other_controller_file);
        }};

        destination other_controller_file {{
            file("{controller_file}");
        }};

        destination other_controller {{
            network(
                "{controller_other_ip}"
                port({controller_port})
                transport("udp")
            );
        }};

        log {{
            source({LOG_SOURCE});
            filter(f_not_smb);
            filter(f_not_mdns);
            filter(f_not_nginx);
            destination(other_controller);
        }};
    """)

    with open(SYSLOG_NG_CONF, "w") as f:
        f.write(syslog_conf)

    with open("/etc/logrotate.d/truenas-ha", "w") as f:
        for file in [controller_file]:
            f.write(textwrap.dedent(f"""\
                {file} {{
                    daily
                    missingok
                    rotate 10
                    notifempty
                    create 640 root adm
                }}
            """))


def use_syslog_dataset(middleware):
    systemdataset = middleware.call_sync("systemdataset.config")

    if systemdataset["syslog"]:
        try:
            return middleware.call_sync("cache.get", "use_syslog_dataset")
        except KeyError:
            pass

        if not middleware.call_sync("system.is_enterprise"):
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

            os.mkdir("/var/log", 0o755)

        reconfigure_logging(middleware)

        return

    log_path = os.path.join(systemdataset["path"], f"syslog-{systemdataset['uuid']}", "log")
    if os.path.exists(log_path):
        # log directory exists, pick up any new files or
        # directories and create them. Existing files will be
        # appended. This is done this way so that ownership and
        # permissions are always preserved.

        if not os.path.islink("/var/log"):
            for item in os.listdir("/var/log"):
                dst = os.path.join(log_path, item)
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
        os.mkdir(log_path)
        os.chmod(log_path, 0o755)
        os.chown(log_path, 0, 0)
        subprocess.run(f"rsync -avz /var/log/* {shlex.quote(log_path + '/')}", shell=True,
                       stdout=subprocess.DEVNULL)

    symlink = False
    if os.path.islink("/var/log"):
        if os.readlink("/var/log") != log_path:
            os.unlink("/var/log")
            symlink = True
    else:
        shutil.rmtree("/var/log")
        symlink = True
    if symlink:
        os.symlink(log_path, "/var/log")

    reconfigure_logging(middleware)


def reconfigure_logging(middleware):
    p = subprocess.run(["systemctl", "restart", "systemd-journald"], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, encoding="utf-8", errors="ignore")
    if p.returncode != 0:
        logger.warning("Unable to restart systemd-journald: %s", p.stdout)

    middleware.call_sync("core.reconfigure_logging")


def render(service, middleware):
    generate_syslog_conf(middleware)
    generate_ha_syslog(middleware)
    configure_syslog(middleware)
