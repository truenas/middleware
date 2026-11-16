from __future__ import annotations

import asyncio
import hashlib
import io
import os
import tarfile
import typing

import aiohttp

from middlewared.api.current import ZFSResourceCreateArgsData, ZFSResourceQuery, ZFSResourceSnapshotCreateArgsData
from middlewared.job import JobCancelledException
from middlewared.service import CallError, ServiceContext, ValidationErrors
from middlewared.utils.network import INTERNET_TIMEOUT

from .dataset import ensure_datasets
from .utils import container_dataset, container_dataset_mountpoint

if typing.TYPE_CHECKING:
    from middlewared.job import Job


REGISTRY_URL = "https://images.sys.truenas.net/streams"
TIMEOUT = aiohttp.ClientTimeout(total=None, connect=INTERNET_TIMEOUT, sock_read=INTERNET_TIMEOUT)
CHUNK_SIZE = 1024 * 1024


def _session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(raise_for_status=True, trust_env=True, timeout=TIMEOUT, read_bufsize=1 << 20)


async def query_registry_images(context: ServiceContext) -> dict[str, typing.Any]:
    await context.middleware.call('network.general.will_perform_activity', 'container')

    try:
        async with _session() as session, session.get(f"{REGISTRY_URL}/v1/images.json") as resp:
            return await resp.json(content_type=None)  # type: ignore[no-any-return]
    except (aiohttp.ClientError, TimeoutError, ValueError) as e:
        raise CallError(f'Failed to query container image registry: {e}')


async def pull(context: ServiceContext, job: Job, pool: str, image: dict[str, typing.Any]) -> str:
    """
    Pull image.
    """
    suffix = f'images/{image["name"]}:{image["version"]}'
    dataset_name = os.path.join(container_dataset(pool), suffix)
    snapshot_name = f'{dataset_name}@image'
    if await context.call2(context.s.zfs.resource.snapshot.exists, snapshot_name):
        # Image dataset already exists, no action needed.
        return snapshot_name

    verrors = ValidationErrors()
    products = (await query_registry_images(context))["products"]
    if (product := products.get(image["name"])) is None:
        verrors.add("name", "Image does not exist in the registry.")
    elif (product_version := product["versions"].get(image["version"])) is None:
        verrors.add("version", "Version does not exist in the registry.")

    verrors.check()

    item = product_version['items']['root.tar.xz']
    url = item['path']

    await ensure_datasets(context, pool)
    if await context.call2(
        context.s.zfs.resource.list_impl,
        ZFSResourceQuery(paths=[dataset_name], properties=None)
    ):
        # Orphan dataset without a snapshot. Probably leftover from a
        # previous `pull` attempt that failed and did not clean up
        # properly. Delete it.
        await context.call2(context.s.zfs.resource.destroy_impl, dataset_name, bypass=True)

    await context.call2(
        context.s.zfs.resource.create_impl,
        ZFSResourceCreateArgsData(path=dataset_name, create_ancestors=True, bypass=True),
    )
    mountpoint = f'/mnt{container_dataset_mountpoint(pool)}/{suffix}'
    tarball_path = os.path.join(mountpoint, 'image.tar')

    def open_tarball() -> io.BufferedWriter:
        return open(tarball_path, 'wb')

    def extract() -> None:
        progress = 80
        with open(tarball_path, 'rb') as raw, tarfile.open(fileobj=raw, mode='r|*') as tar:
            for member in tar:
                if job.aborted_event.is_set():
                    raise JobCancelledException()

                tar.extract(member, path=mountpoint)
                if (new_progress := 80 + min(15, raw.tell() * 15 // item['size'])) != progress:
                    progress = new_progress
                    job.set_progress(progress, 'Extracting image files...')

    extraction: asyncio.Task[None] | None = None
    try:
        try:
            job.set_progress(0, 'Connecting to image repository...')
            sha256 = hashlib.sha256()
            async with _session() as session, session.get(url) as resp:
                total_size = resp.content_length or item['size']
                total_size_mb = total_size / (1024 * 1024)
                downloaded_size = 0
                progress = -1
                with await context.to_thread(open_tarball) as f:
                    async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                        await context.to_thread(f.write, chunk)
                        sha256.update(chunk)
                        downloaded_size += len(chunk)

                        # Report download progress (0-80% of total progress)
                        if (new_progress := min(80, downloaded_size * 80 // total_size)) != progress:
                            progress = new_progress
                            job.set_progress(
                                progress,
                                f'Downloading image: {downloaded_size / (1024 * 1024):.1f}MB / {total_size_mb:.1f}MB'
                            )

            if sha256.hexdigest() != item['sha256']:
                raise CallError(
                    f'Downloaded image {image["name"]}:{image["version"]} failed checksum verification'
                )

            job.set_progress(80, 'Extracting image files...')
            extraction = context.create_task(context.to_thread(extract))
            await asyncio.shield(extraction)
        except (aiohttp.ClientError, TimeoutError) as e:
            raise CallError(f'Failed to download image from {url}: {e}')
        except (tarfile.TarError, OSError) as e:
            raise CallError(f'Failed to extract image tarball: {e}')

        job.set_progress(95, 'Cleaning up temporary files...')
        await context.to_thread(os.remove, tarball_path)

        job.set_progress(98, 'Creating ZFS snapshot...')
        await context.call2(context.s.zfs.resource.snapshot.create_impl, ZFSResourceSnapshotCreateArgsData(
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
        await context.call2(context.s.zfs.resource.destroy_impl, dataset_name, bypass=True)
        raise
