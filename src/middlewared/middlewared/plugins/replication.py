from middlewared.schema import accepts, Dict, Str
from middlewared.service import private, CallError, Service
from middlewared.utils import Popen

import base64
import errno
import os
import subprocess


class ReplicationService(Service):

    @private
    async def ssh_keyscan(self, host, port):
        proc = await Popen([
            "/usr/bin/ssh-keyscan",
            "-p", str(port),
            "-T", "2",
            str(host),
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        key, errmsg = await proc.communicate()
        if proc.returncode != 0 or not key:
            if not errmsg:
                errmsg = 'ssh key scan failed for unknown reason'
            else:
                errmsg = errmsg.decode()
            raise ValueError(errmsg)
        return key.decode()

    @private
    @accepts(Dict(
        'replication-pair-data',
        Str('hostname', required=True),
        Str('public-key', required=True),
        Str('user'),
    ))
    async def pair(self, data):
        """
        Receives public key, storing it to accept SSH connection and return
        pertinent SSH data of this machine.
        """
        service = await self.middleware.call('datastore.query', 'services.services', [('srv_service', '=', 'ssh')], {'get': True})
        ssh = await self.middleware.call('datastore.query', 'services.ssh', None, {'get': True})
        try:
            user = await self.middleware.call('datastore.query', 'account.bsdusers', [('bsdusr_username', '=', data.get('user') or 'root')], {'get': True})
        except IndexError:
            raise ValueError('User "{}" does not exist'.format(data.get('user')))

        if user['bsdusr_home'].startswith('/nonexistent'):
            raise CallError(f'User home directory does not exist', errno.ENOENT)

        # Make sure SSH is enabled
        if not service['srv_enable']:
            await self.middleware.call('datastore.update', 'services.services', service['id'], {'srv_enable': True})
            await self.middleware.call('notifier.start', 'ssh')

            # This might be the first time of the service being enabled
            # which will then result in new host keys we need to grab
            ssh = await self.middleware.call('datastore.query', 'services.ssh', None, {'get': True})

        if not os.path.exists(user['bsdusr_home']):
            raise ValueError('Homedir {} does not exist'.format(user['bsdusr_home']))

        # If .ssh dir does not exist, create it
        dotsshdir = os.path.join(user['bsdusr_home'], '.ssh')
        if not os.path.exists(dotsshdir):
            os.mkdir(dotsshdir)
            os.chown(dotsshdir, user['bsdusr_uid'], user['bsdusr_group']['bsdgrp_gid'])

        # Write public key in user authorized_keys for SSH
        authorized_keys_file = f'{dotsshdir}/authorized_keys'
        with open(authorized_keys_file, 'a+') as f:
            f.seek(0)
            if data['public-key'] not in f.read():
                f.write('\n' + data['public-key'])

        ssh_hostkey = '{0} {1}\n{0} {2}\n{0} {3}\n'.format(
            data['hostname'],
            base64.b64decode(ssh['ssh_host_rsa_key_pub'].encode()).decode(),
            base64.b64decode(ssh['ssh_host_ecdsa_key_pub'].encode()).decode(),
            base64.b64decode(ssh['ssh_host_ed25519_key_pub'].encode()).decode(),
        )

        return {
            'ssh_port': ssh['ssh_tcpport'],
            'ssh_hostkey': ssh_hostkey,
        }
