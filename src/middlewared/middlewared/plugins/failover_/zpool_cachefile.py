from pathlib import Path

from middlewared.service import Service
from middlewared.schema import Str, accepts
from middlewared.plugins.pool import ZPOOL_CACHE_FILE

ZPOOL_CACHE_FILE_SAVED = f'{ZPOOL_CACHE_FILE}.saved'
ZPOOL_CACHE_FILE_OVERWRITE = f'{ZPOOL_CACHE_FILE}.overwrite'


class FailoverZpoolCacheFileService(Service):
    class Config:
        private = True
        namespace = 'failover.zpool.cachefile'

    @accepts(Str('event', enum=['MASTER', 'BACKUP', 'SYNC'], default='MASTER'))
    def setup(self, event):
        saved = Path(ZPOOL_CACHE_FILE_SAVED)
        default = Path(ZPOOL_CACHE_FILE)
        overwrite = Path(ZPOOL_CACHE_FILE_OVERWRITE)
        saved_stat = default_stat = overwrite_stat = None
        for i in [[saved, saved_stat], [default, default_stat], [overwrite, overwrite_stat]]:
            try:
                i[1] = i[0].stat()
            except FileNotFoundError:
                continue

        if event == 'MASTER':
            if (saved_stat and default_stat) and (saved_stat.mtime < default_stat.mtime):
                # we're becoming master which means on backup
                # event we modify the save cache file first and
                # if the pool is successfully exported then the
                # default cachefile is updated and the zpool entry
                # is removed from that file. This is done by zfs
                # itself and not us. That behavior is counter
                # intuitive to what we're trying to do so that's
                # why we save the cachefile before we export
                saved.rename(default.as_posix())
            elif saved_stat and not default_stat:
                saved.rename(default.as_posix())
        elif event == 'BACKUP' and default_stat:
            # means we're becoming backup so we need to save
            # the zpool cachefile before we export the zpools
            saved.write_bytes(default.read_bytes())
        elif event == 'SYNC' and overwrite_stat:
            # a zpool was created/updated on the active controller
            # and the newly created zpool cachefile was sent to this
            # controller so we need to overwrite
            overwrite.rename(default.as_posix())

        default.touch(exist_ok=True)
        if not event == 'BACKUP':
            saved.unlink(missing_ok=True)
        overwrite.unlink(missing_ok=True)
