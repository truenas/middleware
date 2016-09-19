from collections import defaultdict
from middlewared.schema import accepts, Int
from middlewared.service import CRUDService, Service, private

import boto3
import os
import subprocess
import sys


class BackupService(CRUDService):

    def sync(self, id):

        backup = self.middleware.call('datastore.query', 'storage.cloudreplication', [('id', '=', id)], {'get': True})
        if not backup:
            raise ValueError("Unknown id")

        tasks = self.middleware.call('datastore.query', 'storage.task', [('task_filesystem', '=', backup['filesystem'])])
        if not tasks:
            raise ValueError("No periodic snapshot tasks found")

        recursive = False
        for task in tasks:
            if task['task_recursive']:
                recursive = True
                break

        # TODO: Get manifest and find snapshots there
        remote_snapshots = []

        # Calculate delta between remote and local
        proc = subprocess.Popen([
            '/sbin/zfs', 'list',
            '-o', 'name',
            '-H',
        ] + (['-r'] if recursive else []) + [backup['filesystem']],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        datasets = proc.communicate()[0].strip().split('\n')
        assert proc.returncode == 0

        local_snapshots = defaultdict(list)
        for snapshot in self.middleware.call('zfs.snapshot.query'):
            local_snapshots[snapshot['dataset']].append(snapshot)

        for dataset, snapshots in local_snapshots.iteritems():
            snapshots.sort(key=lambda x: x['properties']['createtxg']['rawvalue'])

        send_snapshots = []
        # Send new snapshots to remote
        for snapshot_to, snapshot_from in send_snapshots:
            read_fd, write_fd = os.pipe()
            if os.fork() == 0:
                os.dup2(write_fd, 1)
                try:
                    for i in os.listdir('/dev/fd'):
                        if i != '1':
                            os.close(int(i))
                except OSError:
                    pass
                os.execv('/sbin/zfs', ['/sbin/zfs', 'send', '-V', '-p'] + (['-i', snapshot_from] if snapshot_from else []) + [snapshot_to])

            else:
                os.close(write_fd)
                while True:
                    read = os.read(read_fd, 1024 * 1024)
                    if read == b'':
                        break


class BackupS3Service(Service):

    class Config:
        namespace = 'backup.s3'

    @accepts(Int('id'))
    def get_buckets(self, id):
        """Returns buckets from a given S3 credential."""
        credential = self.middleware.call('datastore.query', 'system.cloudcredentials', [('id', '=', id)], {'get': True})

        s3 = boto3.client(
            's3',
            aws_access_key_id=credential['attributes'].get('access_key'),
            aws_secret_access_key=credential['attributes'].get('secret_key'),
        )

        buckets = []
        for bucket in s3.list_buckets()['Buckets']:
            buckets.append({
                'name': bucket['Name'],
                'creation_date': bucket['CreationDate'],
            })

        return buckets
