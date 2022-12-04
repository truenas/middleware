import middlewared.sqlalchemy as sa

from middlewared.plugins.boot import BOOT_POOL_NAME_VALID
from middlewared.schema import Bool, Dict, Int, List, Ref, Str
from middlewared.service import accepts, CallError, CRUDService, private, returns
from middlewared.service_exception import InstanceNotFound


class PoolModel(sa.Model):
    __tablename__ = 'storage_volume'

    id = sa.Column(sa.Integer(), primary_key=True)
    vol_name = sa.Column(sa.String(120), unique=True)
    vol_guid = sa.Column(sa.String(50))
    vol_encrypt = sa.Column(sa.Integer(), default=0)
    vol_encryptkey = sa.Column(sa.String(50))


class EncryptedDiskModel(sa.Model):
    __tablename__ = 'storage_encrypteddisk'

    id = sa.Column(sa.Integer(), primary_key=True)
    encrypted_volume_id = sa.Column(sa.ForeignKey('storage_volume.id', ondelete='CASCADE'))
    encrypted_disk_id = sa.Column(sa.ForeignKey('storage_disk.disk_identifier', ondelete='SET NULL'), nullable=True)
    encrypted_provider = sa.Column(sa.String(120), unique=True)


class PoolService(CRUDService):

    ENTRY = Dict(
        'pool_entry',
        Int('id', required=True),
        Str('name', required=True),
        Str('guid', required=True),
        Int('encrypt', required=True),
        Str('encryptkey', required=True),
        Str('encryptkey_path', null=True, required=True),
        Bool('is_decrypted', required=True),
        Str('status', required=True),
        Str('path', required=True),
        Dict(
            'scan',
            additional_attrs=True,
            required=True,
            null=True,
            example={
                'function': None,
                'state': None,
                'start_time': None,
                'end_time': None,
                'percentage': None,
                'bytes_to_process': None,
                'bytes_processed': None,
                'bytes_issued': None,
                'pause': None,
                'errors': None,
                'total_secs_left': None,
            }
        ),
        Bool('is_upgraded'),
        Bool('healthy', required=True),
        Bool('warning', required=True),
        Str('status_detail', required=True, null=True),
        Int('size', required=True, null=True),
        Int('allocated', required=True, null=True),
        Int('free', required=True, null=True),
        Int('freeing', required=True, null=True),
        Str('fragmentation', required=True, null=True),
        Str('size_str', required=True, null=True),
        Str('allocated_str', required=True, null=True),
        Str('free_str', required=True, null=True),
        Str('freeing_str', required=True, null=True),
        Dict(
            'autotrim',
            required=True,
            additional_attrs=True,
            example={
                'parsed': 'off',
                'rawvalue': 'off',
                'source': 'DEFAULT',
                'value': 'off',
            }
        ),
        Dict(
            'topology',
            List('data', required=True),
            List('log', required=True),
            List('cache', required=True),
            List('spare', required=True),
            List('special', required=True),
            List('dedup', required=True),
            required=True,
            null=True,
        )
    )

    class Config:
        datastore = 'storage.volume'
        datastore_extend = 'pool.pool_extend'
        datastore_extend_context = 'pool.pool_extend_context'
        datastore_prefix = 'vol_'
        event_send = False
        cli_namespace = 'storage.pool'

    @accepts(Str('name'))
    @returns(Ref('pool_entry'))
    async def get_instance_by_name(self, name):
        """
        Returns pool with name `name`. If `name` is not found, Validation error is raised.
        """
        pool = await self.query([['name', '=', name]])
        if not pool:
            raise InstanceNotFound(f'Pool {name} does not exist')

        return pool[0]

    @private
    @accepts(Str('pool_name'))
    @returns(Ref('pool_entry'))
    async def pool_normalize_info(self, pool_name):
        """
        Returns the current state of 'pool_name' including all vdevs, properties and datasets.

        Common method for `pool.pool_extend` and `boot.get_state` returning a uniform
        data structure for its consumers.
        """
        rv = {
            'name': pool_name,
            'path': '/' if pool_name in BOOT_POOL_NAME_VALID else f'/mnt/{pool_name}',
            'status': 'OFFLINE',
            'scan': None,
            'topology': None,
            'healthy': False,
            'warning': False,
            'status_detail': None,
            'size': None,
            'allocated': None,
            'free': None,
            'freeing': None,
            'fragmentation': None,
            'size_str': None,
            'allocated_str': None,
            'free_str': None,
            'freeing_str': None,
            'autotrim': {
                'parsed': 'off',
                'rawvalue': 'off',
                'source': 'DEFAULT',
                'value': 'off'
            },
            'encryptkey_path': None,
            'is_decrypted': True,
        }

        if info := await self.middleware.call('zfs.pool.query', [('name', '=', pool_name)]):
            info = info[0]
            rv.update({
                'status': info['status'],
                'scan': info['scan'],
                'topology': await self.middleware.call('pool.transform_topology', info['groups']),
                'healthy': info['healthy'],
                'warning': info['warning'],
                'status_detail': info['status_detail'],
                'size': info['properties']['size']['parsed'],
                'allocated': info['properties']['allocated']['parsed'],
                'free': info['properties']['free']['parsed'],
                'freeing': info['properties']['freeing']['parsed'],
                'fragmentation': info['properties']['fragmentation']['parsed'],
                'size_str': info['properties']['size']['rawvalue'],
                'allocated_str': info['properties']['allocated']['rawvalue'],
                'free_str': info['properties']['free']['rawvalue'],
                'freeing_str': info['properties']['freeing']['rawvalue'],
                'autotrim': info['properties']['autotrim'],
            })

        return rv

    @private
    def pool_extend_context(self, rows, extra):
        return {
            "extra": extra,
        }

    @private
    def pool_extend(self, pool, context):

        """
        If pool is encrypted we need to check if the pool is imported
        or if all geli providers exist.
        """
        if context['extra'].get('is_upgraded'):
            pool['is_upgraded'] = self.middleware.call_sync('pool.is_upgraded_by_name', pool['name'])

        # WebUI expects the same data as in `boot.get_state`
        pool |= self.middleware.call_sync('pool.pool_normalize_info', pool['name'])
        return pool
