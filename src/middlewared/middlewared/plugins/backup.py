from middlewared.schema import accepts, Int
from middlewared.service import CRUDService, Service, item_method, job, private

import boto3
import gevent
import gevent.fileobject
import os
import subprocess
import re
import tempfile

CHUNK_SIZE = 5 * 1024 * 1024


class BackupService(CRUDService):

    @item_method
    @accepts(Int('id'))
    @job(lock='backup')
    def sync(self, job, id):

        backup = self.middleware.call('datastore.query', 'tasks.cloudsync', [('id', '=', id)], {'get': True})
        if not backup:
            raise ValueError("Unknown id")

        credential = self.middleware.call('datastore.query', 'system.cloudcredentials', [('id', '=', backup['credential']['id'])], {'get': True})
        if not credential:
            raise ValueError("Backup credential not found.")

        if credential['provider'] == 'AMAZON':
            return self.middleware.call('backup.s3.sync', job, backup, credential)
        else:
            raise NotImplementedError('Unsupported provider: {}'.format(
                credential['provider']
            ))


class BackupS3Service(Service):

    class Config:
        namespace = 'backup.s3'

    @private
    def get_client(self, id):
        credential = self.middleware.call('datastore.query', 'system.cloudcredentials', [('id', '=', id)], {'get': True})

        client = boto3.client(
            's3',
            aws_access_key_id=credential['attributes'].get('access_key'),
            aws_secret_access_key=credential['attributes'].get('secret_key'),
        )
        return client

    @accepts(Int('id'))
    def get_buckets(self, id):
        """Returns buckets from a given S3 credential."""
        client = self.get_client(id)
        buckets = []
        for bucket in client.list_buckets()['Buckets']:
            buckets.append({
                'name': bucket['Name'],
                'creation_date': bucket['CreationDate'],
            })

        return buckets

    @private
    def sync(self, job, backup, credential):
        # Use a temporary file to store s3cmd config file
        with tempfile.NamedTemporaryFile() as f:
            # Make sure only root can read it ad there is sensitive data
            os.chmod(f.name, 0o600)

            fg = gevent.fileobject.FileObject(f.file, 'w', close=False)
            fg.write("""[default]
access_key = {access_key}
secret_key = {secret_key}
""".format(
                access_key=credential['attributes']['access_key'],
                secret_key=credential['attributes']['secret_key'],
            ))
            fg.flush()

            args = [
                '/usr/local/bin/s3cmd',
                '-c', f.name,
                '--progress',
                'sync',
                backup['path'],
                's3://{}'.format(backup['attributes']['bucket']),
            ]

            def check_progress(job, proc):
                RE_FILENUM = re.compile(r'\'(?P<src>.+)\' -> \'(?P<dst>.+)\'\s*\[(?P<current>\d+) of (?P<total>\d+)\]')
                while True:
                    read = proc.stdout.readline()
                    if read == b'':
                        break
                    if read[0] != '\r':
                        reg = RE_FILENUM.search(read)
                        if reg:
                            job.set_progress(None, '{}/{} {} -> {}'.format(
                                reg.group('current'),
                                reg.group('total'),
                                reg.group('src'),
                                reg.group('dst'),
                            ))

            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            gevent.spawn(check_progress, job, proc)
            stderr = proc.communicate()[1]
            if proc.returncode != 0:
                raise ValueError('s3cmd failed: {}'.format(stderr))
            return True

    @private
    def put(self, backup, filename, read_fd):
        client = self.get_client(backup['id'])
        folder = backup['attributes']['folder'] or ''
        key = os.path.join(folder, filename)
        parts = []
        idx = 1

        try:
            with os.fdopen(read_fd, 'rb') as f:
                fg = gevent.fileobject.FileObject(f, 'rb', close=False)
                mp = client.create_multipart_upload(
                    Bucket=backup['attributes']['bucket'],
                    Key=key
                )

                while True:
                    chunk = fg.read(CHUNK_SIZE)
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
    def get(self, backup, filename, write_fd):
        client = self.get_client(backup['id'])
        folder = backup['attributes']['folder'] or ''
        key = os.path.join(folder, filename)
        obj = client.get_object(
            Bucket=backup['attributes']['bucket'],
            Key=key
        )

        with os.fdopen(write_fd, 'wb') as f:
            fg = gevent.fileobject.FileObject(f, 'wb', close=False)
            while True:
                chunk = obj['Body'].read(CHUNK_SIZE)
                if chunk == b'':
                    break
                fg.write(chunk)
