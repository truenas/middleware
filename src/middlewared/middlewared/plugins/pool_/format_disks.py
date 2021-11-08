from os import unlink, chmod
from tempfile import NamedTemporaryFile
from concurrent.futures import ThreadPoolExecutor, as_completed

from middlewared.service import private, Service


class PoolService(Service):

    @private
    def format_and_encrypt_disks(self, job, disks, options=None):
        """
        This does a few things:
            1. wipes the disks
            2. formats the disks with a freebsd-zfs partition label
            3. formats the disks with a freebsd-swap partition label (if necessary)
            4. encrypt disks (only on update method and on existing GELI pools)
        """
        self.middleware.call_sync('disk.sed_unlock_all')  # unlock any SED drives
        swapgb = self.middleware.call_sync('system.advanced.config')['swapondrive']
        total_disks = len(disks)
        options = options or {}

        with ThreadPoolExecutor(max_workers=16) as exc:
            # The called methods `subprocess` out many times for each disk
            # so this is painful on systems with large amount of disks.
            # The best we can really do right now without implementing gpart code
            # natively in python (cython or ctypes wrapper maybe??)
            futures = [exc.submit(
                self.middleware.call_sync('disk.format', k, swapgb if v['create_swap'] else 0, False))
                for k, v in disks.items()
            ]
            for idx, fut in enumerate(as_completed(futures), start=1):
                try:
                    fut.result()
                except TypeError:
                    # `disk.format` method returns None which isn't callable
                    # so this crash is expected
                    job.set_progress(15, f'Formatted disk {idx} of {total_disks}')

            # we do not allow the creation of new GELI based zpools, however,
            # we still allow updates to them so this method is also called then.
            if options.get('enc_keypath'):
                pass_file = None
                if options.get('passphrase'):
                    # called when attaching disks to a GELI encrypted zpool
                    with NamedTemporaryFile(mode='w+', dir='/tmp', delete=False) as p:
                        chmod(p.name, 0o600)
                        p.write(options['passphrase'])
                        p.flush()
                        options['passphrase_path'] = pass_file = p.name

                futures = [exc.submit(
                    self.middleware.call_sync(
                        'disk.encrypt', k, options['enc_keypath'], options.get('passphrase_path'))
                    )
                    for k in disks
                ]
                try:
                    for idx, fut in enumerate(as_completed(futures), start=1):
                        fut.result()
                        job.set_progress(25, f'Encrypted disk {idx} of {total_disks}')
                finally:
                    try:
                        unlink(pass_file)
                    except (TypeError, FileNotFoundError):
                        # TypeError if pass_file = None
                        # FileNotFoundError to be "proper" in case
                        # something else removes that file before we do
                        pass
