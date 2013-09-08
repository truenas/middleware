from subprocess import Popen, PIPE
import hashlib
import os
import platform

plexmediaserver_pbi_path = "/usr/pbi/plexmediaserver-" + platform.machine()
plexmediaserver_etc_path = os.path.join(plexmediaserver_pbi_path, "etc")
plexmediaserver_mnt_path = os.path.join(plexmediaserver_pbi_path, "mnt")
plexmediaserver_fcgi_pidfile = "/var/run/plexmediaserver_fcgi_server.pid"
plexmediaserver_fcgi_wwwdir = os.path.join(plexmediaserver_pbi_path, "www")
plexmediaserver_control = "/usr/local/etc/rc.d/plexmediaserver"
plexmediaserver_icon = os.path.join(plexmediaserver_pbi_path, "default.png")
plexmediaserver_oauth_file = os.path.join(plexmediaserver_pbi_path, ".oauth")


def get_rpc_url(request):
    return 'http%s://%s:%s/plugins/json-rpc/v1/' % (
        's' if request.is_secure() else '',
        request.META.get("SERVER_ADDR"),
        request.META.get("SERVER_PORT"),
        )


def get_plexmediaserver_oauth_creds():
    f = open(plexmediaserver_oauth_file)
    lines = f.readlines()
    f.close()

    key = secret = None
    for l in lines:
        l = l.strip()

        if l.startswith("key"):
            pair = l.split("=")
            if len(pair) > 1:
                key = pair[1].strip()

        elif l.startswith("secret"):
            pair = l.split("=")
            if len(pair) > 1:
                secret = pair[1].strip()

    return key, secret
