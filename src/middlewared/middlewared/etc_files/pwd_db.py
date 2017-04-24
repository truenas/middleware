import subprocess


def render(service, middleware):
    proc = subprocess.Popen([
        '/usr/sbin/pwd_mkdb',
        '/etc/master.passwd',
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
