import os
import paramiko
from time import sleep
import socket
import sys

sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.storage.models import Replication

def check_ssh(ip, port, user, key_file, initial_wait=0, interval=0, retries=1):
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys("/etc/ssh/ssh_known_hosts")

    sleep(initial_wait)

    for x in range(retries):
        try:
            ssh.connect(ip, port, username=user, key_filename=key_file)
            return True
        except (paramiko.BadHostKeyException, paramiko.AuthenticationException, 
                paramiko.SSHException, socket.error) as e:
            print e
            sleep(interval)
    return False

replication_tasks = Replication.objects.all()
for replication in replication_tasks:
    print "Replication task: %s" % replication
    if not replication.repl_enabled:
        print("%s replication not enabled" % replication)
    remote = replication.repl_remote.ssh_remote_hostname.__str__()
    remote_port = replication.repl_remote.ssh_remote_port
    if replication.repl_remote.ssh_remote_dedicateduser_enabled:
        user = replication.repl_remote.ssh_remote_dedicateduser
    else:
        user = "root"
    if check_ssh(remote, remote_port, user, "/data/ssh/replication"):
        print "Status: OK"
        print
    else:
        print "Status: Failed"
        print
