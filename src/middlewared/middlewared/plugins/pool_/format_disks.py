from concurrent.futures import ThreadPoolExecutor, as_completed

from middlewared.service import private, Service


class PoolService(Service):

    @private
    def format_disks(self, job, disks):
        """
        This does a few things:
            1. wipes the disks (max of 16 in parallel using native threads)
            2. formats the disks with a freebsd-zfs partition label
            3. formats the disks with a freebsd-swap partition lable (if necessary)
        """
        self.middleware.call_sync('disk.sed_unlock_all')  # unlock any SED drives
        swapgb = self.middleware.call_sync('system.advanced.config')['swapondrive']
        total_disks = len(disks)
        with ThreadPoolExecutor(max_workers=16) as exc:
            # The called methods `subprocess` out many times for each disk
            # so this is painful on systems with large amount of disks.
            # This is, unfortunately, the best we can really do right now
            # without implementing gpart code natively in python.
            # (cython or ctypes wrapper maybe???)
            futures = [exc.submit(
                self.middleware.call_sync('disk.format', k, swapgb if v['create_swap'] else 0, False))
                for k, v in disks.items()
            ]
            for idx, fut in enumerate(as_completed(futures), start=1):
                try:
                    fut.result()
                except TypeError:
                    # `disk.format` returns None which isn't callable
                    # so this exception is expected and means it's complete
                    job.set_progress(15, f'Formatted disk {idx} of {total_disks}')
