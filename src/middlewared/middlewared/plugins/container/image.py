import os
import tarfile

import requests

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerImagePullArgs, ContainerImagePullResult,
)
from middlewared.service import CallError, job, Service


class ContainerImageService(Service):

    class Config:
        cli_namespace = 'service.container.image'
        namespace = 'container.image'
        role_prefix = 'CONTAINER_IMAGE'

    @api_method(ContainerImagePullArgs, ContainerImagePullResult, roles=['CONTAINER_IMAGE_WRITE'])
    @job()
    def pull(self, job, url, name):
        """
        Pull image.
        """
        config = self.middleware.call_sync('container.config.config')
        if config['image_dataset'] is None:
            raise CallError('Please set container image dataset first.')

        dataset_name = f'{config["image_dataset"]}/{name}'
        mountpoint = self.middleware.call_sync('pool.dataset.create', {'name': dataset_name})['mountpoint']

        # Download tarball from URL
        try:
            job.set_progress(0, 'Connecting to image repository...')
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Get total file size for progress calculation
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            # Save tarball to mountpoint
            tarball_path = os.path.join(mountpoint, 'image.tar')
            with open(tarball_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # Report download progress (0-80% of total progress)
                    if total_size > 0:
                        download_progress = min(80, int((downloaded_size / total_size) * 80))
                        job.set_progress(download_progress, f'Downloading image: {downloaded_size / (1024*1024):.1f}MB / {total_size / (1024*1024):.1f}MB')
                    else:
                        job.set_progress(40, f'Downloading image: {downloaded_size / (1024*1024):.1f}MB')
            
            # Extract tarball to mountpoint
            job.set_progress(80, 'Extracting image files...')
            with tarfile.open(tarball_path, 'r:*') as tar:
                members = tar.getmembers()
                total_members = len(members)
                
                for i, member in enumerate(members):
                    tar.extract(member, path=mountpoint)
            
            # Clean up the tarball file
            job.set_progress(95, 'Cleaning up temporary files...')
            os.remove(tarball_path)
            
            # Create ZFS snapshot
            job.set_progress(98, 'Creating ZFS snapshot...')
            self.middleware.call_sync('zfs.snapshot.create', {
                'dataset': dataset_name,
                'name': 'image'
            })
            
            job.set_progress(100, 'Image pull completed successfully')
            
        except requests.RequestException as e:
            raise CallError(f'Failed to download image from {url}: {str(e)}')
        except (tarfile.TarError, OSError) as e:
            raise CallError(f'Failed to extract image tarball: {str(e)}')
