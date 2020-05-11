# -*- coding=utf-8 -*-
import humanfriendly


class UpdateHandler(object):

    def __init__(self, service, job, download_proportion=50):
        self.service = service
        self.job = job

        self.download_proportion = download_proportion

        self._current_package_index = None
        self._packages_count = None

    def check_handler(self, index, pkg, pkgList):
        self._current_package_index = index - 1
        self._packages_count = len(pkgList)

        pkgname = '%s-%s' % (
            pkg.Name(),
            pkg.Version(),
        )

        self.job.set_progress((self._current_package_index / self._packages_count) * self.download_proportion,
                              'Downloading {}'.format(pkgname))

    def get_handler(
        self, method, filename, size=None, progress=None, download_rate=None
    ):
        if self._current_package_index is None or self._packages_count is None or not progress:
            return

        if size:
            try:
                size = humanfriendly.format_size(int(size))
            except Exception:
                pass

        if download_rate:
            try:
                download_rate = humanfriendly.format_size(int(download_rate)) + "/s"
            except Exception:
                pass

        job_progress = (
            ((self._current_package_index + progress / 100) / self._packages_count) * self.download_proportion)
        filename = filename.rsplit('/', 1)[-1]
        if size and download_rate:
            self.job.set_progress(
                job_progress,
                'Downloading {}: {} ({}%) at {}'.format(
                    filename,
                    size,
                    progress,
                    download_rate,
                )
            )
        else:
            self.job.set_progress(
                job_progress,
                'Downloading {} ({}%)'.format(
                    filename,
                    progress,
                )
            )

    def install_handler(self, index, name, packages):
        total = len(packages)
        self.job.set_progress(
            self.download_proportion + (index / total) * (100 - self.download_proportion),
            'Installing {} ({}/{})'.format(name, index, total),
        )
