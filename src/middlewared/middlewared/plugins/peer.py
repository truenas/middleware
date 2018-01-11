from middlewared.schema import accepts, Dict, Int, Ref, Str
from middlewared.service import CRUDService, CallError, filterable, private
from middlewared.utils import Popen

import subprocess
import asyncssh
import os
import base64

REPLICATION_KEY = '/data/ssh/replication.pub'


class PeerService(CRUDService):

    class Config:
        namespace = "peer"

    @filterable
    async def query(self, filters=None, options=None):
        return await self.middleware.call('datastore.query', 'peers.peer', filters, options)

    @accepts(Dict(
        'peer',
        Str('peer_type', enum=['s3', 'ssh']),
        additional_attrs=True,
        register=True,
    ))
    async def do_create(self, peer):
        peer_type = peer.get('peer_type')
        return await self.middleware.call(
            f'peer.{peer_type}.do_create',
            peer,
        )

    @accepts(Int('id'), Ref('peer'))
    async def do_update(self, id, peer):
        peer_type = peer.get('peer_type')
        if not peer_type:
            peer_data = await self.query([('id', '=', id)], {'get': True})
            peer_type = peer_data['peer_type']
        return await self.middleware.call(
            f'peer.{peer_type}.do_update',
            id,
            peer,
        )

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete',
            'peers.peer',
            id,
        )


class SSHPeerService(CRUDService):

    class Config:
        namespace = 'peer.ssh'

    @filterable
    async def query(self, filters=None, options=None):
        return await self.middleware.call('datastore.query', 'peers.ssh_peer', filters, options)

    @accepts(Dict(
        'peer-ssh',
        Str('name'),
        Str('description'),
        Str('peer_type'),
        Int('ssh_port'),
        Str('ssh_remote_hostname'),
        Str('ssh_remote_user'),
        Str('ssh_remote_hostkey'),
        register=True,
    ))
    async def do_create(self, data):
        return await self.middleware.call(
            'datastore.insert',
            'peers.ssh_peer',
            data,
        )

    @accepts(Int('id'), Ref('peer-ssh'))
    async def do_update(self, id, data):
        return await self.middleware.call(
            'datastore.update',
            'peers.ssh_peer',
            id,
            data,
        )

    @accepts()
    def public_key(self):
        """
        Get the public SSH replication key.
        """
        if (os.path.exists(REPLICATION_KEY) and os.path.isfile(REPLICATION_KEY)):
            with open(REPLICATION_KEY, 'r') as f:
                key = f.read()
        else:
            key = None
        return key

    @accepts(
        Str('host', required=True),
        Int('port', required=True),
    )
    async def ssh_keyscan(self, host, port):
        """
        Scan the SSH key on `host`:`port`.
        """
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
            raise CallError(errmsg)
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

    async def verify_connection(self, id):
        peer = await self.query([('id', '=', id)], {'get': True})

        if peer:
            try:
                async with asyncssh.connect(
                    peer['ssh_remote_hostname'],
                    port=peer['ssh_port'],
                    username=peer['ssh_remote_user']) as conn:

                    return True

            except (OSError, asyncssh.Error) as e:
                raise CallError(f'Failed to connect to the host:{e}')


class S3PeerService(CRUDService):

    class Config:
        namespace = 'peer.s3'

    @filterable
    async def query(self, filters=None, options=None):
        return await self.middleware.call('datastore.query', 'peers.s3_peer', filters, options)

    @accepts(Dict(
        'peer-s3',
        Str('name'),
        Str('description'),
        Str('peer_type'),
        Str('s3_access_key'),
        Str('s3_secret_key'),
        register=True,
    ))
    async def do_create(self, data):
        return await self.middleware.call(
            'datastore.insert',
            'peers.s3_peer',
            data,
        )

    @accepts(Int('id'), Ref('peer-s3'))
    async def do_update(self, id, data):
        return await self.middleware.call(
            'datastore.update',
            'peers.s3_peer',
            id,
            data,
        )
