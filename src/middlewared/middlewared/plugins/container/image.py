import os
import tarfile

import requests

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerImageQueryRegistryArgs, ContainerImageQueryRegistryResult, ZFSResourceQuery,
    ZFSResourceSnapshotCreateQuery,
)
from middlewared.plugins.container.utils import container_dataset, container_dataset_mountpoint
from middlewared.plugins.pool_.utils import CreateImplArgs
from middlewared.service import CallError, job, private, Service, ValidationErrors
from middlewared.utils.network import INTERNET_TIMEOUT

REGISTRY_URL = "https://images.sys.truenas.net/streams"


class ContainerImageService(Service):
    class Config:
        cli_namespace = 'service.container.image'
        namespace = 'container.image'
        role_prefix = 'CONTAINER_IMAGE'

    @api_method(ContainerImageQueryRegistryArgs, ContainerImageQueryRegistryResult, roles=['CONTAINER_IMAGE_WRITE'])
    def query_registry(self):
        """
        Query images available in the images registry.
        """
        products = self.query_registry_images()["products"]

        return [
            {
                "name": name,
                "versions": [
                    {
                        "version": version
                    }
                    for version in product["versions"].keys()
                ]
            }
            for name, product in products.items()
        ]

    @private
    def query_registry_images(self):
        self.middleware.call_sync('network.general.will_perform_activity', 'container')

        r = requests.get(f"{REGISTRY_URL}/v1/images.json", timeout=INTERNET_TIMEOUT)
        r.raise_for_status()
        return r.json()

    @job()
    @private
    def pull(self, job, pool, image):
        """
        Pull image.
        """
        suffix = f'images/{image["name"]}:{image["version"]}'
        dataset_name = os.path.join(container_dataset(pool), suffix)
        snapshot_name = f'{dataset_name}@image'
        if self.call_sync2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(paths=[dataset_name], properties=None)
        ):
            # Check if the snapshot exists
            if not self.call_sync2(self.s.zfs.resource.snapshot.exists, snapshot_name):
                # Orphan dataset without a snapshot. Probably leftover from a
                # previous `pull` attempt that failed and did not clean up
                # properly. Delete it.
                self.call_sync2(self.s.zfs.resource.destroy_impl, dataset_name)
            else:
                # Image dataset already exists, no action needed.
                return snapshot_name

        self.middleware.call_sync('container.ensure_datasets', pool)
        self.middleware.call_sync(
            'pool.dataset.create_impl',
            CreateImplArgs(
                name=dataset_name,
                create_ancestors=True,
                ztype='FILESYSTEM',
            ),
        )
        try:
            verrors = ValidationErrors()
            products = self.query_registry_images()["products"]
            if (product := products.get(image["name"])) is None:
                verrors.add("name", "Image does not exist in the registry.")
            elif (product_version := product["versions"].get(image["version"])) is None:
                verrors.add("version", "Version does not exist in the registry.")

            verrors.check()

            # Download tarball from URL
            url = product_version['items']['root.tar.xz']['path']  # noqa
            try:
                job.set_progress(0, 'Connecting to image repository...')
                response = requests.get(url, stream=True)
                response.raise_for_status()

                # Get total file size for progress calculation
                total_size = int(response.headers.get('content-length', 0))
                total_size_mb = total_size / (1024 * 1024)

                downloaded_size = 0

                mountpoint = f'/mnt{container_dataset_mountpoint(pool)}/{suffix}'
                # Save tarball to mountpoint
                tarball_path = os.path.join(mountpoint, 'image.tar')
                try:
                    with open(tarball_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            downloaded_size_mb = downloaded_size / (1024 * 1024)

                            # Report download progress (0-80% of total progress)
                            if total_size > 0:
                                download_progress = min(80, int((downloaded_size / total_size) * 80))
                                job.set_progress(
                                    download_progress,
                                    f'Downloading image: {downloaded_size_mb:.1f}MB / {total_size_mb:.1f}MB'
                                )
                            else:
                                job.set_progress(40, f'Downloading image: {total_size_mb:.1f}MB')

                    # Extract tarball to mountpoint
                    job.set_progress(80, 'Extracting image files...')
                    with tarfile.open(tarball_path, 'r:*') as tar:
                        members = tar.getmembers()

                        for i, member in enumerate(members):
                            tar.extract(member, path=mountpoint)
                finally:
                    # Clean up the tarball file
                    job.set_progress(95, 'Cleaning up temporary files...')
                    os.remove(tarball_path)

                # Create ZFS snapshot
                job.set_progress(98, 'Creating ZFS snapshot...')
                self.call_sync2(self.s.zfs.resource.snapshot.create_impl, ZFSResourceSnapshotCreateQuery(
                    dataset=dataset_name,
                    name='image'
                ))

                job.set_progress(100, 'Image pull completed successfully')
                return snapshot_name
            except requests.RequestException as e:
                raise CallError(f'Failed to download image from {url}: {str(e)}')
            except (tarfile.TarError, OSError) as e:
                raise CallError(f'Failed to extract image tarball: {str(e)}')
        except Exception:
            self.call_sync2(self.s.zfs.resource.destroy_impl, dataset_name)
            raise


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'container', 'Container images registry')
