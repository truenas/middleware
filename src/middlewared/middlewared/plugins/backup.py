from middlewared.schema import accepts, Bool, Dict, Int, Patch Ref, Str
from middlewared.service import CRUDService, Service, item_method, filterable, job, private
from middlewared.utils import Popen

import asyncio
import boto3
import os
import subprocess
import re
import tempfile

CHUNK_SIZE = 5 * 1024 * 1024


class BackupCredentialService(CRUDService):

    class Config:
        namespace = 'backup.credential'

    @filterable
    def query(self, filters=None, options=None):
        return self.middleware.call('datastore.query', 'system.cloudcredentials', filters, options)

    @accepts(Dict(
        'backup-credential',
        Str('name'),
        Str('provider', enum=[
            'AMAZON',
        ]),
        Dict('attributes', additional_attrs=True),
        register=True,
    ))
    def do_create(self, data):
        return self.middleware.call(
            'datastore.insert',
            'system.cloudcredentials',
            data,
        )

    @accepts(Int('id'), Ref('backup-credential'))
    def do_update(self, id, data):
        return self.middleware.call(
            'datastore.update',
            'system.cloudcredentials',
            id,
            data,
        )

    @accepts(Int('id'))
    def do_delete(self, id):
        return self.middleware.call(
            'datastore.delete',
            'system.cloudcredentials',
            id,
        )


class BackupService(CRUDService):

    @accepts(Ref('query-filters'), Ref('query-options'))
    def query(self, filters=None, options=None):
        return self.middleware.call('datastore.query', 'tasks.cloudsync', filters, options)

    def _clean_credential(self, data):
        credential = self.middleware.call('datastore.query', 'system.cloudcredentials', [('id', '=', data['credential'])], {'get': True})
        assert credential is not None

        if credential['provider'] == 'AMAZON':
            data['attributes']['region'] = self.middleware.call('backup.s3.get_bucket_location', credential['id'], data['attributes']['bucket'])
        else:
            raise NotImplementedError('Invalid provider: {}'.format(credential['provider']))

    @accepts(Dict(
        'backup',
        Str('description'),
        Str('direction', enum=['PUSH', 'PULL']),
        Str('path'),
        Int('credential'),
        Str('minute'),
        Str('hour'),
        Str('daymonth'),
        Str('dayweek'),
        Str('month'),
        Dict('attributes', additional_attrs=True),
        Bool('enabled'),
        register=True,
    ))
    async def do_create(self, data):
        """
        Creates a new backup entry.

        .. examples(websocket)::

          Create a new backup using amazon s3 attributes, which is supposed to run every hour.

            :::javascript
            {
              "id": "6841f242-840a-11e6-a437-00e04d680384",
              "msg": "method",
              "method": "backup.create",
              "params": [{
                "description": "s3 sync",
                "path": "/mnt/tank",
                "credential": 1,
                "minute": "00",
                "hour": "*",
                "daymonth": "*",
                "month": "*",
                "attributes": {
                  "bucket": "mybucket",
                  "folder": ""
                },
                "enabled": true
              }]
            }
        """
        self._clean_credential(data)
        pk = await self.middleware.call('datastore.insert', 'tasks.cloudsync', data)
        await self.middleware.call('notifier.restart', 'cron')
        return pk

    @accepts(Int('id'), Patch('backup', 'backup_update', ('attr', {'update': True})))
    async def do_update(self, id, data):
        """
        Updates the backup entry `id` with `data`.
        """
        backup = await self.middleware.call(
            'datastore.query',
            'tasks.cloudsync',
            [('id', '=', id)],
            {'get': True},
        )
        assert backup is not None
        # credential is a foreign key for now
        if backup['credential']:
            backup['credential'] = backup['credential']['id']

        backup.update(data)
        self._clean_credential(backup)
        await self.middleware.call('datastore.update', 'tasks.cloudsync', id, backup)
        await self.middleware.call('notifier.restart', 'cron')

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Deletes backup entry `id`.
        """
        await self.middleware.call('datastore.delete', 'tasks.cloudsync', id)
        await self.middleware.call('notifier.restart', 'cron')

    @item_method
    @accepts(Int('id'))
    @job(lock=lambda args: 'backup:{}'.format(args[-1]))
    async def sync(self, job, id):
        """
        Run the backup job `id`, syncing the local data to remote.
        """

        backup = await self.middleware.call('datastore.query', 'tasks.cloudsync', [('id', '=', id)], {'get': True})
        if not backup:
            raise ValueError("Unknown id")

        credential = await self.middleware.call('datastore.query', 'system.cloudcredentials', [('id', '=', backup['credential']['id'])], {'get': True})
        if not credential:
            raise ValueError("Backup credential not found.")

        if credential['provider'] == 'AMAZON':
            return await self.middleware.call('backup.s3.sync', job, backup, credential)
        else:
            raise NotImplementedError('Unsupported provider: {}'.format(
                credential['provider']
            ))


class BackupS3Service(Service):

    class Config:
        namespace = 'backup.s3'

    @private
    async def get_client(self, id):
        credential = await self.middleware.call('datastore.query', 'system.cloudcredentials', [('id', '=', id)], {'get': True})

        client = boto3.client(
            's3',
            aws_access_key_id=credential['attributes'].get('access_key'),
            aws_secret_access_key=credential['attributes'].get('secret_key'),
        )
        return client

    @accepts(Int('id'))
    async def get_buckets(self, id):
        """Returns buckets from a given S3 credential."""
        client = await self.get_client(id)
        buckets = []
        for bucket in client.list_buckets()['Buckets']:
            buckets.append({
                'name': bucket['Name'],
                'creation_date': bucket['CreationDate'],
            })

        return buckets

    @accepts(Int('id'), Str('name'))
    async def get_bucket_location(self, id, name):
        """
        Returns bucket `name` location (region) from credential `id`.
        """
        client = await self.get_client(id)
        response = client.get_bucket_location(Bucket=name)
        return response['LocationConstraint']

    @private
    async def sync(self, job, backup, credential):
        # Use a temporary file to store s3cmd config file
        with tempfile.NamedTemporaryFile(mode='w+') as f:
            # Make sure only root can read it ad there is sensitive data
            os.chmod(f.name, 0o600)

            f.write("""[remote]
type = s3
env_auth = false
access_key_id = {access_key}
secret_access_key = {secret_key}
region = {region}
""".format(
                access_key=credential['attributes']['access_key'],
                secret_key=credential['attributes']['secret_key'],
                region=backup['attributes']['region'] or '',
            ))
            f.flush()

            args = [
                '/usr/local/bin/rclone',
                '--config', f.name,
                '--stats', '1s',
                'sync',
            ]

            remote_path = 'remote:{}{}'.format(
                backup['attributes']['bucket'],
                '/{}'.format(backup['attributes']['folder']) if backup['attributes'].get('folder') else '',
            )

            if backup['direction'] == 'PUSH':
                args.extend([backup['path'], remote_path])
            else:
                args.extend([remote_path, backup['path']])

            async def check_progress(job, proc):
                RE_TRANSF = re.compile(r'Transferred:\s*?(.+)$', re.S)
                read_buffer = ''
                while True:
                    read = proc.stderr.readline().decode()
                    if read == '':
                        break
                    read_buffer += read
                    if len(read_buffer) > 10240:
                        read_buffer = read_buffer[-10240:]
                    reg = RE_TRANSF.search(read)
                    if reg:
                        transferred = reg.group(1).strip()
                        if not transferred.isdigit():
                            job.set_progress(None, transferred)
                return read_buffer

            proc = await Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            check_task = asyncio.ensure_future(check_progress(job, proc))
            await proc.communicate()
            if proc.returncode != 0:
                await asyncio.wait_for(check_task)
                raise ValueError('rclone failed: {}'.format(check_task.result()))
            return True

    @private
    async def put(self, backup, filename, read_fd):
        client = await self.get_client(backup['id'])
        folder = backup['attributes']['folder'] or ''
        key = os.path.join(folder, filename)
        parts = []
        idx = 1

        try:
            with os.fdopen(read_fd, 'rb') as f:
                mp = client.create_multipart_upload(
                    Bucket=backup['attributes']['bucket'],
                    Key=key
                )

                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if chunk == b'':
                        break

                    resp = client.upload_part(
                        Bucket=backup['attributes']['bucket'],
                        Key=key,
                        PartNumber=idx,
                        UploadId=mp['UploadId'],
                        ContentLength=CHUNK_SIZE,
                        Body=chunk
                    )

                    parts.append({
                        'ETag': resp['ETag'],
                        'PartNumber': idx
                    })

                    idx += 1

                client.complete_multipart_upload(
                    Bucket=backup['attributes']['bucket'],
                    Key=key,
                    UploadId=mp['UploadId'],
                    MultipartUpload={
                        'Parts': parts
                    }
                )
        finally:
            pass

    @private
    async def get(self, backup, filename, write_fd):
        client = await self.get_client(backup['id'])
        folder = backup['attributes']['folder'] or ''
        key = os.path.join(folder, filename)
        obj = client.get_object(
            Bucket=backup['attributes']['bucket'],
            Key=key
        )

        with os.fdopen(write_fd, 'wb') as f:
            while True:
                chunk = obj['Body'].read(CHUNK_SIZE)
                if chunk == b'':
                    break
                f.write(chunk)

    @private
    async def ls(self, cred_id, bucket, path):
        client = await self.get_client(cred_id)
        obj = client.list_objects_v2(
            Bucket=bucket,
            Prefix=path,
        )
        if obj['KeyCount'] == 0:
            return []
        return obj['Contents']
