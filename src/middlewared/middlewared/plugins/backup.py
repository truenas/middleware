from azure.storage import CloudStorageAccount
from google.cloud import storage

from middlewared.schema import accepts, Bool, Dict, Int, Patch, Ref, Str
from middlewared.service import (
    CallError, CRUDService, Service, ValidationErrors, item_method, filterable, job, private
)
from middlewared.utils import Popen

import asyncio
import base64
import boto3
import codecs
from Crypto import Random
from Crypto.Cipher import AES
from Crypto.Util import Counter
import errno
import json
import os
import shutil
import subprocess
import re
import requests
import tempfile

CHUNK_SIZE = 5 * 1024 * 1024


async def rclone(job, backup, config):
    # Use a temporary file to store rclone file
    with tempfile.NamedTemporaryFile(mode='w+') as f:
        # Make sure only root can read it as there is sensitive data
        os.chmod(f.name, 0o600)

        remote_path = 'remote:{}{}'.format(
            backup['attributes']['bucket'],
            '/{}'.format(backup['attributes']['folder']) if backup['attributes'].get('folder') else '',
        )

        if backup["encryption"]:
            f.write("[encrypted]\n")
            f.write("type = crypt\n")
            f.write("remote = %s\n" % remote_path)
            f.write("filename_encryption = %s\n" % ("standard" if backup["filename_encryption"] else "off"))
            f.write("password = %s\n" % rclone_encrypt_password(backup["encryption_password"]))
            f.write("password2 = %s\n" % rclone_encrypt_password(backup["encryption_salt"]))

            remote_path = "encrypted:/"

        f.write("[remote]\n")
        for k, v in config.items():
            f.write(f"{k} = {v}\n")

        f.flush()

        args = [
            '/usr/local/bin/rclone',
            '--config', f.name,
            '-v',
            '--stats', '1s',
            backup['transfer_mode'].lower(),
        ]

        if backup['direction'] == 'PUSH':
            args.extend([backup['path'], remote_path])
        else:
            args.extend([remote_path, backup['path']])

        proc = await Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        check_task = asyncio.ensure_future(rclone_check_progress(job, proc))
        await proc.wait()
        if proc.returncode != 0:
            await asyncio.wait_for(check_task, None)
            raise ValueError("rclone failed")
        return True


async def rclone_check_progress(job, proc):
    RE_TRANSF = re.compile(r'Transferred:\s*?(.+)$', re.S)
    while True:
        read = (await proc.stdout.readline()).decode()
        job.logs_fd.write(read.encode("utf-8", "ignore"))
        if read == '':
            break
        reg = RE_TRANSF.search(read)
        if reg:
            transferred = reg.group(1).strip()
            if not transferred.isdigit():
                job.set_progress(None, transferred)


def rclone_encrypt_password(password):
    key = bytes([0x9c, 0x93, 0x5b, 0x48, 0x73, 0x0a, 0x55, 0x4d,
                 0x6b, 0xfd, 0x7c, 0x63, 0xc8, 0x86, 0xa9, 0x2b,
                 0xd3, 0x90, 0x19, 0x8e, 0xb8, 0x12, 0x8a, 0xfb,
                 0xf4, 0xde, 0x16, 0x2b, 0x8b, 0x95, 0xf6, 0x38])

    iv = Random.new().read(AES.block_size)
    counter = Counter.new(128, initial_value=int(codecs.encode(iv, "hex"), 16))
    cipher = AES.new(key, AES.MODE_CTR, counter=counter)
    encrypted = iv + cipher.encrypt(password.encode("utf-8"))
    return base64.urlsafe_b64encode(encrypted).decode("ascii").rstrip("=")


class BackupCredentialService(CRUDService):

    class Config:
        namespace = 'backup.credential'

    @filterable
    async def query(self, filters=None, options=None):
        return await self.middleware.call('datastore.query', 'system.cloudcredentials', filters, options)

    @accepts(Dict(
        'backup-credential',
        Str('name'),
        Str('provider', enum=[
            'AMAZON',
            'AZURE',
            'BACKBLAZE',
            'GCLOUD',
        ]),
        Dict('attributes', additional_attrs=True),
        register=True,
    ))
    async def do_create(self, data):
        return await self.middleware.call(
            'datastore.insert',
            'system.cloudcredentials',
            data,
        )

    @accepts(Int('id'), Ref('backup-credential'))
    async def do_update(self, id, data):
        return await self.middleware.call(
            'datastore.update',
            'system.cloudcredentials',
            id,
            data,
        )

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete',
            'system.cloudcredentials',
            id,
        )


class BackupService(CRUDService):

    class Config:
        datastore = 'tasks.cloudsync'
        datastore_extend = 'backup._extend'

    @private
    async def _extend(self, backup):
        backup['encryption_password'] = await self.middleware.call('notifier.pwenc_decrypt',
                                                                   backup['encryption_password'])
        backup['encryption_salt'] = await self.middleware.call('notifier.pwenc_decrypt', backup['encryption_salt'])

        return backup

    @private
    async def _compress(self, backup):
        if 'encryption_password' in backup:
            backup['encryption_password'] = await self.middleware.call('notifier.pwenc_encrypt',
                                                                       backup['encryption_password'])
        if 'encryption_salt' in backup:
            backup['encryption_salt'] = await self.middleware.call('notifier.pwenc_encrypt', backup['encryption_salt'])

        return backup

    @private
    async def _validate(self, verrors, name, data):
        if data['encryption']:
            if not data['encryption_password']:
                verrors.add(f'{name}.encryption_password', 'This field is required when encryption is enabled')

            if not data['encryption_salt']:
                verrors.add(f'{name}.encryption_salt', 'This field is required when encryption is enabled')

        credential = await self.middleware.call('datastore.query', 'system.cloudcredentials', [('id', '=', data['credential'])], {'get': True})
        if credential is None:
            verrors.add(f'{name}.credential', f'Credential {data["credential"]} not found', errno.ENOENT)
            return

        if credential['provider'] == 'AMAZON':
            data['attributes']['region'] = await self.middleware.call('backup.s3.get_bucket_location', credential['id'], data['attributes']['bucket'])
        elif credential['provider'] in ('AZURE', 'BACKBLAZE', 'GCLOUD'):
            # AZURE|BACKBLAZE|GCLOUD does not need validation nor new data at this stage
            pass
        else:
            verrors.add(f'{name}.provider', f'Invalid provider: {credential["provider"]}')

        if credential['provider'] == 'AMAZON':
            if data['attributes'].get('encryption') not in (None, 'AES256'):
                verrors.add(f'{name}.attributes.encryption', 'Encryption should be null or "AES256"')

    @accepts(Dict(
        'backup',
        Str('description'),
        Str('direction', enum=['PUSH', 'PULL']),
        Str('transfer_mode', enum=['SYNC', 'COPY', 'MOVE']),
        Str('path'),
        Int('credential'),
        Bool('encryption', default=False),
        Bool('filename_encryption', default=False),
        Str('encryption_password'),
        Str('encryption_salt'),
        Str('minute'),
        Str('hour'),
        Str('daymonth'),
        Str('dayweek'),
        Str('month'),
        Dict('attributes', additional_attrs=True),
        Bool('enabled', default=True),
        register=True,
    ))
    async def do_create(self, backup):
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

        verrors = ValidationErrors()

        await self._validate(verrors, 'backup', backup)

        if verrors:
            raise verrors

        backup = await self._compress(backup)

        pk = await self.middleware.call('datastore.insert', 'tasks.cloudsync', backup)
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

        verrors = ValidationErrors()

        await self._validate(verrors, 'backup_update', backup)

        if verrors:
            raise verrors

        backup = await self._compress(backup)

        await self.middleware.call('datastore.update', 'tasks.cloudsync', id, backup)
        await self.middleware.call('notifier.restart', 'cron')
        return id

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Deletes backup entry `id`.
        """
        await self.middleware.call('datastore.delete', 'tasks.cloudsync', id)
        await self.middleware.call('notifier.restart', 'cron')

    @item_method
    @accepts(Int('id'))
    @job(lock=lambda args: 'backup:{}'.format(args[-1]), lock_queue_size=1, logs=True)
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

        return await self._call_provider_method(credential['provider'], 'sync', job, backup, credential)

    @accepts(Int('credential_id'), Str('bucket'), Str('path'))
    async def is_dir(self, credential_id, bucket, path):
        credential = await self.middleware.call('datastore.query', 'system.cloudcredentials',
                                                [('id', '=', credential_id)], {'get': True})
        if not credential:
            raise ValueError("Backup credential not found.")

        return await self._call_provider_method(credential['provider'], 'is_dir', credential_id, bucket, path)

    @private
    async def _call_provider_method(self, provider, method, *args, **kwargs):
        try:
            plugin = {
                'AMAZON': 's3',
                'AZURE': 'azure',
                'BACKBLAZE': 'b2',
                'GCLOUD': 'gcs',
            }[provider]
        except KeyError:
            raise NotImplementedError(f'Unsupported provider: {provider}')

        return await self.middleware.call(f'backup.{plugin}.{method}', *args, **kwargs)


class BackupS3Service(Service):

    class Config:
        namespace = 'backup.s3'

    @private
    async def get_client(self, id):
        credential = await self.middleware.call('datastore.query', 'system.cloudcredentials', [('id', '=', id)], {'get': True})

        client = boto3.client(
            's3',
            endpoint_url=credential['attributes'].get('endpoint', '').strip() or None,
            aws_access_key_id=credential['attributes'].get('access_key'),
            aws_secret_access_key=credential['attributes'].get('secret_key'),
        )
        return client

    @accepts(Int('id'))
    async def get_buckets(self, id):
        """Returns buckets from a given S3 credential."""
        client = await self.get_client(id)
        buckets = []
        for bucket in (await self.middleware.run_in_io_thread(client.list_buckets))['Buckets']:
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
        response = (await self.middleware.run_in_io_thread(client.get_bucket_location, Bucket=name))
        return response['LocationConstraint']

    @private
    async def sync(self, job, backup, credential):
        return await rclone(job, backup, {
            "type": "s3",
            "env_auth": "false",
            "access_key_id": credential['attributes']['access_key'],
            "secret_access_key": credential['attributes']['secret_key'],
            "region": backup['attributes']['region'] or '',
            "endpoint": credential['attributes'].get("endpoint", ""),
            "server_side_encryption": backup['attributes'].get('encryption') or '',
        })

    @private
    async def put(self, backup, filename, f):
        client = await self.get_client(backup['id'])
        folder = backup['attributes']['folder'] or ''
        key = os.path.join(folder, filename)
        parts = []
        idx = 1

        try:
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
    async def get(self, backup, filename, f):
        client = await self.get_client(backup['id'])
        folder = backup['attributes']['folder'] or ''
        key = os.path.join(folder, filename)
        obj = client.get_object(
            Bucket=backup['attributes']['bucket'],
            Key=key
        )

        shutil.copyfileobj(obj['Body'], f)

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

    @private
    async def is_dir(self, cred_id, bucket, path):
        client = await self.get_client(cred_id)
        objects_list = await self.middleware.run_in_thread(
            client.list_objects_v2,
            Bucket=bucket,
            Prefix=path,
        )
        for obj in objects_list.get('Contents', []):
            if obj['Key'] == path or obj['Key'].startswith(f'{path}/'):
                return True
        return False


class BackupB2Service(Service):

    class Config:
        namespace = 'backup.b2'

    def __get_auth(self, id):
        credential = self.middleware.call_sync('datastore.query', 'system.cloudcredentials', [('id', '=', id)], {'get': True})

        r = requests.get(
            'https://api.backblazeb2.com/b2api/v1/b2_authorize_account',
            auth=(credential['attributes'].get('account_id'), credential['attributes'].get('app_key')),
        )
        if r.status_code != 200:
            raise CallError(f'Invalid request: {r.text}')
        return r.json()

    @accepts(Int('id'))
    def get_buckets(self, id):
        """Returns buckets from a given B2 credential."""
        auth = self.__get_auth(id)
        r = requests.post(
            f'{auth["apiUrl"]}/b2api/v1/b2_list_buckets',
            headers={
                'Authorization': auth['authorizationToken'],
                'Content-Type': 'application/json',
            },
            data=json.dumps({'accountId': auth['accountId']}),
        )
        if r.status_code != 200:
            raise CallError(f'Invalid B2 request: [{r.status_code}] {r.text}')
        return r.json()['buckets']

    @private
    async def sync(self, job, backup, credential):
        return await rclone(job, backup, {
            "type": "b2",
            "env_auth": "false",
            "account": credential['attributes']['account_id'],
            "key": credential['attributes']['app_key'],
            "endpoint": "",
        })

    @private
    def is_dir(self, cred_id, bucket, path):
        auth = self.__get_auth(cred_id)

        for b in self.get_buckets(cred_id):
            if b['bucketName'] == bucket:
                bucket_id = b['bucketId']
                break
        else:
            raise ValueError("Bucket not found")

        startFileName = None
        while True:
            r = requests.post(
                f'{auth["apiUrl"]}/b2api/v1/b2_list_file_names',
                headers={
                    'Authorization': auth['authorizationToken'],
                    'Content-Type': 'application/json',
                },
                data=json.dumps({'bucketId': bucket_id,
                                 'startFileName': startFileName,
                                 'prefix': path,
                                 'delimiter': '/'}),
            )
            if r.status_code != 200:
                raise CallError(f'Invalid B2 request: [{r.status_code}] {r.text}')
            response = r.json()
            for file in response['files']:
                if file['fileName'] == f'{path}/':
                    return True
            if response['nextFileName'] is None:
                break
            startFileName = response['nextFileName']

        return False


class BackupGCSService(Service):

    class Config:
        namespace = 'backup.gcs'

    def __get_client(self, id):
        credential = self.middleware.call_sync('datastore.query', 'system.cloudcredentials', [('id', '=', id)], {'get': True})

        with tempfile.NamedTemporaryFile(mode='w+') as f:
            # Make sure only root can read it as there is sensitive data
            os.chmod(f.name, 0o600)
            f.write(json.dumps(credential['attributes']['keyfile']))
            f.flush()
            client = storage.Client.from_service_account_json(f.name)

        return client

    @accepts(Int('id'))
    def get_buckets(self, id):
        """Returns buckets from a given B2 credential."""
        client = self.__get_client(id)
        buckets = []
        for i in client.list_buckets():
            buckets.append(i._properties)
        return buckets

    @private
    async def sync(self, job, backup, credential):
        with tempfile.NamedTemporaryFile(mode='w+') as keyf:
            os.chmod(keyf.name, 0o600)

            keyf.write(json.dumps(credential['attributes']['keyfile']))
            keyf.flush()

            return await rclone(job, backup, {
                "type": "google cloud storage",
                "client_id": "",
                "client_secret": "",
                "project_number": "",
                "service_account_file": keyf.name,
            })

    @private
    def is_dir(self, cred_id, bucket, path):
        client = self.__get_client(cred_id)
        bucket = storage.Bucket(client, bucket)
        prefix = f"{path}/"
        for blob in bucket.list_blobs(prefix=prefix):
            if blob.name.startswith(prefix):
                return True
        return False


class BackupAzureService(Service):

    class Config:
        namespace = 'backup.azure'

    def __get_client(self, id):
        credential = self.middleware.call_sync('datastore.query', 'system.cloudcredentials', [('id', '=', id)], {'get': True})

        return CloudStorageAccount(
            credential['attributes'].get('account_name'),
            credential['attributes'].get('account_key'),
        )

    @accepts(Int('id'))
    def get_buckets(self, id):
        client = self.__get_client(id)
        block_blob_service = client.create_block_blob_service()
        buckets = []
        for bucket in block_blob_service.list_containers():
            buckets.append(bucket.name)
        return buckets

    @private
    async def sync(self, job, backup, credential):
        return await rclone(job, backup, {
            "type": "azureblob",
            "account": credential['attributes']['account_name'],
            "key": credential['attributes']['account_key'],
            "endpoint": "",
        })

    @private
    def is_dir(self, cred_id, bucket, path):
        client = self.__get_client(cred_id)
        block_blob_service = client.create_block_blob_service()
        prefix = f"{path}/"
        for blob in block_blob_service.list_blobs(bucket, prefix=prefix):
            if blob.name.startswith(prefix):
                return True
        return False
