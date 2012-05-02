from subprocess import Popen, PIPE
import os
import platform

firefly_pbi_path = "/usr/pbi/firefly-" + platform.machine()
firefly_etc_path = os.path.join(firefly_pbi_path, "etc")
firefly_mnt_path = os.path.join(firefly_pbi_path, "mnt")
firefly_fcgi_pidfile = "/var/run/firefly_fcgi_server.pid"
firefly_fcgi_wwwdir = os.path.join(firefly_pbi_path, "www")
firefly_control = "/usr/local/etc/rc.d/mt-daapd"
firefly_config = os.path.join(firefly_etc_path, "mt-daapd.conf")
firefly_icon = os.path.join(firefly_pbi_path, "default.png")
firefly_oauth_file = os.path.join(firefly_pbi_path, ".oauth")


def get_rpc_url(request):
    return 'http%s://%s/plugins/json-rpc/v1/' % ('s' if request.is_secure() \
            else '', request.get_host(),)


def get_firefly_oauth_creds():
    f = open(firefly_oauth_file)
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


firefly_advanced_vars = {
    "set_cwd": {
        "type": "checkbox",
        "on": "-a",
        },
    "debuglevel": {
        "type": "textbox",
        "opt": "-d",
        },
    "debug_modules": {
        "type": "textbox",
        "opt": "-D",
        },
    "disable_mdns": {
        "type": "checkbox",
        "on": "-m",
        },
    "non_root_user": {
        "type": "checkbox",
        "on": "-y",
        },
    "ffid": {
        "type": "textbox",
        "opt": "-b",
        },
}
