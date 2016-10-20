from middlewared.schema import accepts, Dict, Str
from middlewared.service import private, Service
from middlewared.utils import Popen

import subprocess


class ReplicationService(Service):

    @private
    def ssh_keyscan(self, host, port):
        proc = Popen([
            "/usr/bin/ssh-keyscan",
            "-p", str(port),
            "-T", "2",
            str(host),
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        key, errmsg = proc.communicate()
        if proc.returncode != 0 or not key:
            if not errmsg:
                errmsg = 'ssh key scan failed for unknown reason'
            raise ValueError(errmsg)
        return key

    @private
    @accepts(Dict(
        'replication-pair-data',
        Str('public-key'),
    ))
    def pair(self, data):
        """
        Receives public key, storing it to accept SSH connection and return
        pertinent SSH data of this machine.
        """
        service = self.middleware.call('datastore.query', 'services.services', [('srv_service', '=', 'ssh')], {'get': True})
        ssh = self.middleware.call('datastore.query', 'services.ssh', None, {'get': True})
        root = self.middleware.call('datastore.query', 'account.bsdusers', [('bsdusr_uid', '=', 0)], {'get': True})

        # Make sure SSH is enabled
        if not service['srv_enable']:
            raise ValueError('SSH service is not enabled on remote')

        # Write public key in user authorized_keys for SSH
        authorized_keys_file = '{}/.ssh/authorized_keys'.format(root['bsdusr_home'])
        with open(authorized_keys_file, 'a+') as f:
            f.seek(0)
            if data['public-key'] not in f.read():
                f.write('\n' + data['public-key'])

        return {
            'ssh_port': ssh['ssh_tcpport'],
            'ssh_hostkey': self.ssh_keyscan('localhost', ssh['ssh_tcpport']),
        }
