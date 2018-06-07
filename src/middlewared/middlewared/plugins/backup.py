import json

from middlewared.schema import accepts, Bool, Dict, Int, Patch, Ref, Str
from middlewared.service import (
    CRUDService, Service, filterable, private
)


class BackupCredentialService(CRUDService):

    class Config:
        namespace = 'backup.credential'

    @filterable
    async def query(self, filters=None, options=None):
        result = []
        for data in await self.middleware.call('cloudsync.credentials.query', filters, options):
            provider = data["provider"]
            attributes = data["attributes"]

            if provider == "S3":
                provider = "AMAZON"
                attributes = {
                    "access_key": attributes["access_key_id"],
                    "secret_key": attributes["secret_access_key"],
                    "endpoint": attributes.get("endpoint", ""),
                }

            elif provider == "AZUREBLOB":
                provider = "AZURE"
                attributes = {
                    "account_name": attributes["account"],
                    "account_key": attributes["key"],
                }

            elif provider == "B2":
                provider = "BACKBLAZE"
                attributes = {
                    "account_id": attributes["account"],
                    "app_key": attributes["key"],
                }

            elif provider == "GOOGLE_CLOUD_STORAGE":
                provider = "GCLOUD"
                attributes = {
                    "keyfile": json.loads(attributes["service_account_credentials"]),
                }

            else:
                continue

            data["provider"] = provider
            data["attributes"] = attributes

            result.append(data)

        return result

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
        return (await self.middleware.call('cloudsync.credentials.create', self._proxy(data)))["id"]

    @accepts(Int('id'), Ref('backup-credential'))
    async def do_update(self, id, data):
        return (await self.middleware.call('cloudsync.credentials.update', id, self._proxy(data)))["id"]

    @accepts(Int('id'))
    async def do_delete(self, id):
        await self.middleware.call('cloudsync.credential.delete', id)

    @private
    def _proxy(self, data):
        provider = data["provider"]
        attributes = data["attributes"]

        if provider == "AMAZON":
            provider = "S3"
            attributes = {
                "access_key_id": attributes["access_key"],
                "secret_access_key": attributes["secret_key"],
                "endpoint": attributes.get("endpoint", ""),
            }

        if provider == "AZURE":
            provider = "AZUREBLOB"
            attributes = {
                "account": attributes["account_name"],
                "key": attributes["account_key"],
            }

        if provider == "BACKBLAZE":
            provider = "B2"
            attributes = {
                "account": attributes["account_id"],
                "key": attributes["app_key"],
            }

        if provider == "GCLOUD":
            provider = "GOOGLE_CLOUD_STORAGE"
            attributes = {
                "service_account_credentials": json.dumps(attributes["keyfile"]),
            }

        data["provider"] = provider
        data["attributes"] = attributes

        return data


class BackupService(CRUDService):

    class Config:
        datastore = 'tasks.cloudsync'

    async def query(self, filters=None, options=None):
        result = []
        for data in await self.middleware.call('cloudsync.query', filters, options):
            data['credential'] = data.pop('credentials')

            data["minute"] = data["schedule"].pop("minute"),
            data["hour"] = data["schedule"].pop("hour"),
            data["daymonth"] = data["schedule"].pop("dom"),
            data["month"] = data["schedule"].pop("month"),
            data["dayweek"] = data["schedule"].pop("dow")
            data.pop("schedule")

            result.append(data)
        return result

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
        backup['credentials'] = backup.pop('credential')

        backup["schedule"] = {
            "minute": backup.pop("minute"),
            "hour": backup.pop("hour"),
            "dom": backup.pop("daymonth"),
            "month": backup.pop("month"),
            "dow": backup.pop("dayweek")
        }

        return (await self.middleware.call('cloudsync.create', backup))["id"]

    @accepts(Int('id'), Patch('backup', 'backup_update', ('attr', {'update': True})))
    async def do_update(self, id, data):
        if 'credential' in data:
            data['credentials'] = data.pop('credential')

        if 'minute' in data and 'hour' in data and 'daymonth' in data and 'month' in data and 'dayweek' in data:
            data["schedule"] = {
                "minute": data.pop("minute"),
                "hour": data.pop("hour"),
                "dom": data.pop("daymonth"),
                "month": data.pop("month"),
                "dow": data.pop("dayweek")
            }

        return (await self.middleware.call('cloudsync.update', id, data))["id"]

    @accepts(Int('id'))
    async def do_delete(self, id):
        await self.middleware.call('cloudsync.delete', id)


class BackupS3Service(Service):

    class Config:
        namespace = 'backup.s3'

    @accepts(Int('id'))
    async def get_buckets(self, id):
        return [
            {
                'bucketName': bucket['Name'],
            }
            for bucket in await self.middleware.call('cloudsync.list_buckets', id)
        ]


class BackupB2Service(Service):

    class Config:
        namespace = 'backup.b2'

    @accepts(Int('id'))
    async def get_buckets(self, id):
        return [
            {
                'bucketName': bucket['Name'],
            }
            for bucket in await self.middleware.call('cloudsync.list_buckets', id)
        ]


class BackupGCSService(Service):

    class Config:
        namespace = 'backup.gcs'

    @accepts(Int('id'))
    async def get_buckets(self, id):
        return [
            {
                'bucketName': bucket['Name'],
            }
            for bucket in await self.middleware.call('cloudsync.list_buckets', id)
        ]


class BackupAzureService(Service):

    class Config:
        namespace = 'backup.azure'

    @accepts(Int('id'))
    async def get_buckets(self, id):
        return [
            {
                'bucketName': bucket['Name'],
            }
            for bucket in await self.middleware.call('cloudsync.list_buckets', id)
        ]
