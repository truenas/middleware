from middlewared.schema import accepts, Dict, Int, Ref, Str
from middlewared.service import CRUDService, filterable


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

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete',
            'peers.ssh_peer',
            id,
        )


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

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete',
            'peers.s3_peer',
            id,
        )
