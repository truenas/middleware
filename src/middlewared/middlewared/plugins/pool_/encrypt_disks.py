import os
from tempfile import NamedTemporaryFile
from concurrent.futures import ThreadPoolExecutor, as_completed

from middlewared.service import private, Service


class PoolService(Service):

    @private
    def encrypt_disks(self, job, disks, options):
        """
        This GELI encrypts all the disks in `disks`.
        NOTE: this is only called on pool.update since GELI was deprecated
        for all newly created zpools.
        """
        # we do not allow the creation of new GELI based zpools, however,
        # we still have to support users who created them before we deprecated
        # the parameters in the API. This is here for those users.
        total_disks = len(disks)
        pass_file = None
        if options.get('passphrase'):
            # called when attaching disks to a GELI encrypted zpool
            with NamedTemporaryFile(mode='w+', dir='/tmp', delete=False) as p:
                os.chmod(p.name, 0o600)
                p.write(options['passphrase'])
                p.flush()
                options['passphrase_path'] = pass_file = p.name

        with ThreadPoolExecutor(max_workers=16) as exc:
            # The called methods `subprocess` out many times for each disk
            # so this is painful on systems with large amount of disks.
            # This is, unfortunately, the best we can really do right now
            # without implementing gpart code natively in python.
            # (cython or ctypes wrapper maybe???)
            futures = [
                exc.submit(
                    self.middleware.call_sync(
                        'disk.encrypt', i['devname'].replace('.eli', ''),
                        options['enc_keypath'], options.get('passphrase_path')
                    )
                )
                for i in disks
            ]
            try:
                for idx, fut in enumerate(as_completed(futures), start=1):
                    try:
                        fut.result()
                    except TypeError:
                        # `disk.encrypt` returns a str type which isn't callable
                        # however, it's return data isn't needed so the TypeError
                        # is expected
                        job.set_progress(25, f'Encrypted disk {idx} of {total_disks!r}')
            finally:
                try:
                    os.unlink(pass_file)
                except (TypeError, FileNotFoundError):
                    # TypeError if pass_file = None
                    # FileNotFoundError to be "proper" in case
                    # something else removes that file before we do
                    pass
