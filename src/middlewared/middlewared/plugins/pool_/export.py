import os
import shutil

from middlewared.service import Service, private


class PoolService(Service):

    @private
    def cleanup_after_export(self, poolinfo, opts):
        if poolinfo['encrypt'] > 0:
            try:
                # this is CORE GELI encryption which doesn't exist on SCALE
                # so it means someone upgraded from CORE to SCALE and their
                # db has an entry with a GELI based encrypted pool in it so
                # we'll remove the GELI key files associated with the zpool
                os.remove(poolinfo['encryptkey'])
            except Exception:
                # not fatal, and doesn't really matter since SCALE can't
                # use this zpool anyways
                pass

        try:
            if all((opts['destroy'], opts['cascade'])) and (contents := os.listdir(poolinfo['path'])):
                if len(contents) == 1 and contents[0] == 'ix-applications':
                    # This means:
                    #   1. zpool was destroyed (disks were wiped)
                    #   2. end-user chose to delete all share configuration associated
                    #       to said zpool
                    #   3. somehow ix-applications was the only top-level directory that
                    #       got left behind
                    #
                    # Since all 3 above are true, then we just need to remove this directory
                    # so we don't leave dangling directory(ies) in /mnt.
                    # (i.e. it'll leave something like /mnt/tank/ix-application/blah)
                    shutil.rmtree(poolinfo['path'])
            else:
                # remove top-level directory for zpool (i.e. /mnt/tank (ONLY if it's empty))
                os.rmdir(poolinfo['path'])
        except FileNotFoundError:
            # means the pool was exported and the path where the
            # root dataset (zpool) was mounted was removed
            return
        except Exception:
            self.logger.warning('Failed to remove remaining directories after export', exc_info=True)
