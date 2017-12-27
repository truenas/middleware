from middlewared.schema import accepts, Dict, Int, Ref, Str
from middlewared.service import CRUDService, filterable
import asyncssh



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
