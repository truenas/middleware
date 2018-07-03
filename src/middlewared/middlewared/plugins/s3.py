from middlewared.schema import accepts, Bool, Dict, Dir, Int, Str
from middlewared.validators import Match, Range
from middlewared.service import SystemServiceService, ValidationErrors, private

import os


class S3Service(SystemServiceService):

    class Config:
        service = "s3"
        datastore_prefix = "s3_"
        datastore_extend = "s3.config_extend"

    @private
    async def config_extend(self, s3):
        s3['storage_path'] = s3.pop('disks', None)
        s3.pop('mode', None)
        return s3

    @accepts(Dict(
        's3_update',
        Str('bindip'),
        Int('bindport', validators=[Range(min=1, max=65535)]),
        Str('access_key', validators=[Match("^\w+$")]),
        Str('secret_key', validators=[Match("^\w+$")]),
        Bool('browser'),
        Dir('storage_path'),
        Int('certificate'),
        update=True,
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        for attr, minlen, maxlen in (
            ('access_key', 5, 20),
            ('secret_key', 8, 40),
        ):
            curlen = len(new.get(attr, ''))
            if curlen < minlen or curlen > maxlen:
                verrors.add(
                    f's3_update.{attr}', f'Attribute should be {minlen} to {maxlen} in length'
                )

        if not new['storage_path'] or not os.path.exists(new['storage_path']):
            verrors.add('s3_update.storage_path', 'Storage path is required')

        if verrors:
            raise verrors

        new['disks'] = new.pop('storage_path')

        await self._update_service(old, new)

        if await self.middleware.call('notifier.mp_get_owner', new['disks']) != 'minio':
            await self.middleware.call('notifier.winacl_reset', new['disks'], 'minio', 'minio')

        return await self.config()
