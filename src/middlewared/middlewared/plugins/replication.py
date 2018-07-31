from middlewared.async_validators import resolve_hostname
from middlewared.client import Client
from middlewared.schema import accepts, Bool, Dict, Int, Patch, Str
from middlewared.service import private, CallError, CRUDService, ValidationErrors
from middlewared.utils import Popen
from middlewared.validators import Range, Time

import base64
import errno
import os
import pickle
import re
import subprocess

from datetime import time


REPLICATION_KEY = '/data/ssh/replication.pub'
REPL_RESULTFILE = '/tmp/.repl-result'


class ReplicationService(CRUDService):

    class Config:
        datastore = 'storage.replication'
        datastore_prefix = 'repl_'
        datastore_extend = 'replication.replication_extend'

    @private
    async def replication_extend(self, data):

        remote_data = data.pop('remote')
        data['remote'] = remote_data['id']
        data['remote_dedicateduser_enabled'] = remote_data['ssh_remote_dedicateduser_enabled']
        data['remote_port'] = remote_data['ssh_remote_port']
        data['remote_cipher'] = remote_data['ssh_cipher'].upper()
        data['remote_dedicateduser'] = remote_data['ssh_remote_dedicateduser']
        data['remote_hostkey'] = remote_data['ssh_remote_hostkey']
        data['remote_hostname'] = remote_data['ssh_remote_hostname']

        if not os.path.exists(REPL_RESULTFILE):
            data['lastresult'] = {'msg': 'Waiting'}
        else:
            with open(REPL_RESULTFILE, 'rb') as f:
                file_data = f.read()
            try:
                results = pickle.loads(file_data)
                data['lastresult'] = results[data['id']]
            except Exception:
                data['lastresult'] = {'msg': None}

        progressfile = f'/tmp/.repl_progress_{data["id"]}'
        if os.path.exists(progressfile):
            with open(progressfile, 'r') as f:
                pid = int(f.read())
            title = await self.middleware.call('notifier.get_proc_title', pid)
            if title:
                reg = re.search(r'sending (\S+) \((\d+)%', title)
                if reg:
                    data['status'] = f'Sending {reg.groups()[0]}s {reg.groups()[1]}s'
                else:
                    data['status'] = 'Sending'

        if 'status' not in data:
            data['status'] = data['lastresult'].get('msg')

        data['begin'] = str(data['begin'])
        data['end'] = str(data['end'])
        data['compression'] = data['compression'].upper()

        return data

    @private
    async def validate_data(self, data, schema_name):
        verrors = ValidationErrors()

        remote_hostname = data.pop('remote_hostname')
        await resolve_hostname(
            self.middleware, verrors, f'{schema_name}.remote_hostname', remote_hostname
        )

        remote_dedicated_user_enabled = data.pop('remote_dedicateduser_enabled', False)
        remote_dedicated_user = data.pop('remote_dedicateduser', None)
        if remote_dedicated_user_enabled and not remote_dedicated_user:
            verrors.add(
                f'{schema_name}.remote_dedicateduser',
                'You must select a user when remote dedicated user is enabled'
            )

        if not await self.middleware.call(
                'pool.snapshottask.query',
                [('filesystem', '=', data.get('filesystem'))]
        ):
            verrors.add(
                f'{schema_name}.filesystem',
                'Invalid Filesystem'
            )

        remote_mode = data.pop('remote_mode', 'MANUAL')

        remote_port = data.pop('remote_port')

        repl_remote_dict = {
            'ssh_remote_hostname': remote_hostname,
            'ssh_remote_dedicateduser_enabled': remote_dedicated_user_enabled,
            'ssh_remote_dedicateduser': remote_dedicated_user,
            'ssh_cipher': data.pop('remote_cipher', 'STANDARD').lower()
        }

        if remote_mode == 'SEMIAUTOMATIC':
            token = data.pop('remote_token', None)
            if not token:
                verrors.add(
                    f'{schema_name}.remote_token',
                    'This field is required'
                )
        else:
            remote_host_key = data.pop('remote_hostkey', None)
            if not remote_host_key:
                verrors.add(
                    f'{schema_name}.remote_hostkey',
                    'This field is required'
                )
            else:
                repl_remote_dict['ssh_remote_port'] = remote_port
                repl_remote_dict['ssh_remote_hostkey'] = remote_host_key

        if verrors:
            raise verrors

        data['begin'] = time(*[int(v) for v in data.pop('begin').split(':')])
        data['end'] = time(*[int(v) for v in data.pop('end').split(':')])

        data['compression'] = data['compression'].lower()

        data.pop('remote_hostkey', None)
        data.pop('remote_token', None)

        return verrors, data, repl_remote_dict

    @accepts(
        Dict(
            'replication_create',
            Bool('enabled', default=True),
            Bool('followdelete', default=False),
            Bool('remote_dedicateduser_enabled', default=False),
            Bool('remote_https'),
            Bool('userepl', default=False),
            Int('limit', default=0, validators=[Range(min=0)]),
            Int('remote_port', default=22, required=True),
            Str('begin', validators=[Time()]),
            Str('compression', enum=['OFF', 'LZ4', 'PIGZ', 'PLZIP']),
            Str('end', validators=[Time()]),
            Str('filesystem', required=True),
            Str('remote_cipher', enum=['STANDARD', 'FAST', 'DISABLED']),
            Str('remote_dedicateduser'),
            Str('remote_hostkey'),
            Str('remote_hostname', required=True),
            Str('remote_mode', enum=['SEMIAUTOMATIC', 'MANUAL'], required=True),
            Str('remote_token'),
            Str('zfs', required=True),
            register=True
        )
    )
    async def do_create(self, data):

        remote_hostname = data.get('remote_hostname')
        remote_dedicated_user = data.get('remote_dedicateduser')
        remote_port = data.get('remote_port')
        remote_https = data.pop('remote_https', False)
        remote_token = data.get('remote_token')
        remote_mode = data.get('remote_mode')

        verrors, data, repl_remote_dict = await self.validate_data(data, 'replication_create')

        if remote_mode == 'SEMIAUTOMATIC':

            remote_uri = f'ws{"s" if remote_https else ""}://{remote_hostname}:{remote_port}/websocket'

            try:
                with Client(remote_uri) as c:
                    if not c.call('auth.token', remote_token):
                        verrors.add(
                            'replication_create.remote_token',
                            'Please provide a valid token'
                        )
                    else:
                        try:
                            with open(REPLICATION_KEY, 'r') as f:
                                publickey = f.read()

                            call_data = c.call('replication.pair', {
                                'hostname': remote_hostname,
                                'public-key': publickey,
                                'user': remote_dedicated_user,
                            })
                        except Exception as e:
                            raise CallError('Failed to set up replication ' + str(e))
                        else:
                            repl_remote_dict['ssh_remote_port'] = call_data['ssh_port']
                            repl_remote_dict['ssh_remote_hostkey'] = call_data['ssh_hostkey']
            except Exception as e:
                verrors.add(
                    'replication_create.remote_token',
                    f'Failed to connect to remote host {remote_uri} with following exception {e}'
                )

        if verrors:
            raise verrors

        remote_pk = await self.middleware.call(
            'datastore.insert',
            'storage.replremote',
            repl_remote_dict
        )

        await self._service_change('ssh', 'reload')

        data['remote'] = remote_pk

        pk = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        return await self._get_instance(pk)

    @accepts(
        Int('id', required=True),
        Patch(
            'replication_create', 'replication_update',
            ('attr', {'update': True}),
            ('rm', {'name': 'remote_mode'}),
            ('rm', {'name': 'remote_https'}),
            ('rm', {'name': 'remote_token'}),
        )
    )
    async def do_update(self, id, data):

        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

        verrors, new, repl_remote_dict = await self.validate_data(new, 'replication_update')

        new.pop('status')
        new.pop('lastresult')

        await self.middleware.call(
            'datastore.update',
            'storage.replremote',
            new['remote'],
            repl_remote_dict
        )

        await self._service_change('ssh', 'reload')

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        return await self._get_instance(id)

    @accepts(
        Int('id')
    )
    async def do_delete(self, id):

        replication = await self._get_instance(id)

        try:
            if replication['lastsnapshot']:
                zfsname = replication['lastsnapshot'].split('@')[0]
                await self.middleware.call('notifier.zfs_dataset_release_snapshots', zfsname, True)
        except Exception:
            pass

        await self.middleware.call('replication.remove_from_state_file', id)

        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        await self._service_change('ssh', 'reload')

        return response

    @private
    def remove_from_state_file(self, id):
        if os.path.exists(REPL_RESULTFILE):
            with open(REPL_RESULTFILE, 'rb') as f:
                data = f.read()
            try:
                results = pickle.loads(data)
                results.pop(id, None)
                with open(REPL_RESULTFILE, 'wb') as f:
                    f.write(pickle.dumps(results))
            except Exception as e:
                self.logger.debug('Failed to remove replication from state file %s', e)

        progressfile = '/tmp/.repl_progress_%d' % id
        try:
            os.unlink(progressfile)
        except Exception:
            pass

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
