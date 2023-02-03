import logging
import os
import re
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
        result += 'destination(loghost); }};\n'

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
        # filter app mounts messages
        #####################
        filter f_app_mounts {
         program("systemd") and match("mount:" value("MESSAGE")) and match("docker" value("MESSAGE")); or
         program("systemd") and match("mount:" value("MESSAGE")) and match("kubelet" value("MESSAGE"));
        };
        destination d_app_mounts { file("/var/log/app_mounts.log"); };
        log { source(s_src); filter(f_app_mounts); destination(d_app_mounts); };


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
                r' and not filter(f_kube_router) and not filter(f_app_mounts) and ',
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


def render(service, middleware):
    generate_syslog_conf(middleware)
