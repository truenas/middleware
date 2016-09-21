from middlewared.schema import accepts, Int
from middlewared.service import CRUDService, Service, item_method, job, private

import boto3
import gevent
import gevent.fileobject
import os

CHUNK_SIZE = 5 * 1024 * 1024


class BackupService(CRUDService):

    @item_method
    @accepts(Int('id'))
    @job
    def sync(self, job, id):

        backup = self.middleware.call('datastore.query', 'tasks.cloudsync', [('id', '=', id)], {'get': True})
        if not backup:
            raise ValueError("Unknown id")


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
