import asyncio
import hashlib
import os
import tarfile

import aiohttp

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerImageQueryRegistryArgs, ContainerImageQueryRegistryResult, ZFSResourceQuery,
    ZFSResourceSnapshotCreateQuery,
)
from middlewared.job import JobCancelledException
from middlewared.plugins.container.utils import container_dataset, container_dataset_mountpoint
from middlewared.plugins.pool_.utils import CreateImplArgs
from middlewared.service import CallError, job, private, Service, ValidationErrors
from middlewared.utils.network import INTERNET_TIMEOUT

REGISTRY_URL = "https://images.sys.truenas.net/streams"
TIMEOUT = aiohttp.ClientTimeout(total=None, connect=INTERNET_TIMEOUT, sock_read=INTERNET_TIMEOUT)
CHUNK_SIZE = 1024 * 1024


def _session():
    return aiohttp.ClientSession(raise_for_status=True, trust_env=True, timeout=TIMEOUT, read_bufsize=1 << 20)


class ContainerImageService(Service):
    class Config:
        cli_namespace = 'service.container.image'
        namespace = 'container.image'
        role_prefix = 'CONTAINER_IMAGE'

    @api_method(ContainerImageQueryRegistryArgs, ContainerImageQueryRegistryResult, roles=['CONTAINER_IMAGE_WRITE'])
    async def query_registry(self):
        """
        Query images available in the images registry.
        """
        products = (await self.query_registry_images())["products"]

        # Only include versions that have a root.tar.xz (container rootfs).
        # VM-only images (desktop, freebsd, etc.) only ship disk.qcow2.
        result = []
        for name, product in products.items():
            versions = []
            for version, vdata in product["versions"].items():
                if "root.tar.xz" in vdata.get("items", {}):
                    versions.append({"version": version})

            if versions:
                result.append({"name": name, "versions": versions})

        return result

    @private
    async def query_registry_images(self):
        await self.middleware.call('network.general.will_perform_activity', 'container')

        try:
            async with _session() as session, session.get(f"{REGISTRY_URL}/v1/images.json") as resp:
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as e:
            raise CallError(f'Failed to query container image registry: {e}')

    @job(
        lock=lambda args: f'container_image_pull:{args[0]}:{args[1]["name"]}:{args[1]["version"]}',
        lock_queue_size=None,
    )
    @private
    async def pull(self, job, pool, image):
        """
        Pull image.
        """
        suffix = f'images/{image["name"]}:{image["version"]}'
        dataset_name = os.path.join(container_dataset(pool), suffix)
        snapshot_name = f'{dataset_name}@image'
        if await self.call2(self.s.zfs.resource.snapshot.exists, snapshot_name):
            # Image dataset already exists, no action needed.
            return snapshot_name

        verrors = ValidationErrors()
        products = (await self.query_registry_images())["products"]
        if (product := products.get(image["name"])) is None:
            verrors.add("name", "Image does not exist in the registry.")
        elif (product_version := product["versions"].get(image["version"])) is None:
            verrors.add("version", "Version does not exist in the registry.")

        verrors.check()

        item = product_version['items']['root.tar.xz']
        url = item['path']

        await self.middleware.call('container.ensure_datasets', pool)
        if await self.call2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(paths=[dataset_name], properties=None)
        ):
            # Orphan dataset without a snapshot. Probably leftover from a
            # previous `pull` attempt that failed and did not clean up
            # properly. Delete it.
            await self.call2(self.s.zfs.resource.destroy_impl, dataset_name, bypass=True)

        await self.middleware.call(
            'pool.dataset.create_impl',
            CreateImplArgs(
                name=dataset_name,
                create_ancestors=True,
                ztype='FILESYSTEM',
            ),
        )
        mountpoint = f'/mnt{container_dataset_mountpoint(pool)}/{suffix}'
        tarball_path = os.path.join(mountpoint, 'image.tar')

        def open_tarball():
            return open(tarball_path, 'wb')

        def extract():
            progress = 80
            with open(tarball_path, 'rb') as raw, tarfile.open(fileobj=raw, mode='r|*') as tar:
                for member in tar:
                    if job.aborted_event.is_set():
                        raise JobCancelledException()

                    tar.extract(member, path=mountpoint)
                    if (new_progress := 80 + min(15, raw.tell() * 15 // item['size'])) != progress:
                        progress = new_progress
                        job.set_progress(progress, 'Extracting image files...')

        extraction = None
        try:
            try:
                job.set_progress(0, 'Connecting to image repository...')
                sha256 = hashlib.sha256()
                async with _session() as session, session.get(url) as resp:
                    total_size = resp.content_length or item['size']
                    total_size_mb = total_size / (1024 * 1024)
                    downloaded_size = 0
                    progress = -1
                    with await self.context.to_thread(open_tarball) as f:
                        async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                            await self.context.to_thread(f.write, chunk)
                            sha256.update(chunk)
                            downloaded_size += len(chunk)

                            # Report download progress (0-80% of total progress)
                            if (new_progress := min(80, downloaded_size * 80 // total_size)) != progress:
                                progress = new_progress
                                downloaded_size_mb = downloaded_size / (1024 * 1024)
                                job.set_progress(
                                    progress,
                                    f'Downloading image: {downloaded_size_mb:.1f}MB / {total_size_mb:.1f}MB'
                                )

                if sha256.hexdigest() != item['sha256']:
                    raise CallError(
                        f'Downloaded image {image["name"]}:{image["version"]} failed checksum verification'
                    )

                job.set_progress(80, 'Extracting image files...')
                extraction = self.context.create_task(self.context.to_thread(extract))
                await asyncio.shield(extraction)
            except (aiohttp.ClientError, TimeoutError) as e:
                raise CallError(f'Failed to download image from {url}: {e}')
            except (tarfile.TarError, OSError) as e:
                raise CallError(f'Failed to extract image tarball: {e}')

            job.set_progress(95, 'Cleaning up temporary files...')
            await self.context.to_thread(os.remove, tarball_path)

            job.set_progress(98, 'Creating ZFS snapshot...')
            await self.call2(self.s.zfs.resource.snapshot.create_impl, ZFSResourceSnapshotCreateQuery(
                dataset=dataset_name,
                name='image',
                bypass=True,
            ))

            job.set_progress(100, 'Image pull completed successfully')
            return snapshot_name
        except (Exception, asyncio.CancelledError):
            if extraction is not None:
                # A cancel does not stop the extract thread. Destroying the dataset while it writes fails as busy.
                await asyncio.gather(extraction, return_exceptions=True)
            await self.call2(self.s.zfs.resource.destroy_impl, dataset_name, bypass=True)
            raise


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'container', 'Container images registry')
