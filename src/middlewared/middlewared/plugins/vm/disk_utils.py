import errno
import os
import re
import shlex
import subprocess

from middlewared.api import api_method
from middlewared.api.current import (
    VMImportDiskImageArgs, VMImportDiskImageResult, VMExportDiskImageArgs, VMExportDiskImageResult,
)
from middlewared.plugins.zfs_.utils import zvol_name_to_path
from middlewared.service import CallError, Service, job


# Valid Disk Formats we can export
VALID_DISK_FORMATS = ['qcow2', 'qed', 'raw', 'vdi', 'vpc', 'vmdk' ]

class VMService(Service):

    @api_method(VMImportDiskImageArgs, VMImportDiskImageResult, roles=['VM_WRITE'])
    @job(lock_queue_size=1, lock=lambda args: f"zvol_disk_image_{args[-1]['zvol']}")
    def import_disk_image(self, job, data):

        """
        Imports a specified disk image. 

        Utilized qemu-img with the auto-detect functionality to auto-convert
        any supported disk image format to RAW -> ZVOL

        As of this implementation it supports:

        - QCOW2
        - QED
        - RAW
        - VDI
        - VPC
        - VMDK

        `diskimg` is an required parameter for the incoming disk image
        `zvol` is the required target for the imported disk image
        """
        
        if not self.middleware.call_sync('zfs.dataset.query', [('id', '=', data['zvol'])]):
           raise CallError(f"zvol {data['zvol']} does not exist.", errno.ENOENT)

        if os.path.exists(data['diskimg']) is False:
           raise CallError('Disk Image does not exist.', errno.ENOENT)

        if os.path.exists(zvol_name_to_path(data['zvol'])) is False:
           raise CallError('Zvol device does not exist.', errno.ENOENT)

        zvol_device_path = str(zvol_name_to_path(data['zvol']))

        # Use quotes safely and assemble the command
        imgsafe = shlex.quote(data['diskimg'])
        devsafe = shlex.quote(zvol_device_path)
        command = f"qemu-img convert -p -O raw {imgsafe} {devsafe}"
        self.logger.warning('Running Disk Import using: "' + command + '"')

        cp = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)

        re_progress = re.compile(r'(\d+\.\d+)')
        stderr = ''

        for line in iter(cp.stdout.readline, ""):
            progress = re_progress.search(line.lstrip())
            if progress:
                try:
                    progress = round(float(progress.group(1)))
                    job.set_progress(progress, "Disk Import Progress")
                except ValueError:
                    self.logger.warning('Invalid progress in: "' + progress.group(1) + '"')
            else:
                stderr += line
                self.logger.warning('No progress reported from qemu-img: "' + line.lstrip() + '"')
        cp.wait()

        if cp.returncode:
            raise CallError(f'Failed to import disk: {stderr}')

        return True

    @api_method(VMExportDiskImageArgs, VMExportDiskImageResult, roles=['VM_WRITE'])
    @job(lock_queue_size=1, lock=lambda args: f"zvol_disk_image_{args[-1]['zvol']}")
    def export_disk_image(self, job, data):

        """
        Exports a zvol to a formatted VM disk image.

        Utilized qemu-img with the conversion functionality to export a zvol to
        any supported disk image format, from RAW -> ${OTHER}. The resulting file
        will be set to inherit the permissions of the target directory.

        As of this implementation it supports the following {format} options :

        - QCOW2
        - QED
        - RAW
        - VDI
        - VPC
        - VMDK

        `format` is an required parameter for the exported disk image
        `directory` is an required parameter for the export disk image
        `zvol` is the source for the disk image
        """

        if not self.middleware.call_sync('zfs.dataset.query', [('id', '=', data['zvol'])]):
           raise CallError(f"zvol {data['zvol']} does not exist.", errno.ENOENT)

        if os.path.isdir(data['directory']) is False:
           raise CallError(f"Export directory {data['directory']} does not exist.", errno.ENOENT)

        if os.path.exists(zvol_name_to_path(data['zvol'])) is False:
           raise CallError('Zvol device does not exist.', errno.ENOENT)

        # Check that a supported format was specified
        format = data['format'].lower()
        if format not in VALID_DISK_FORMATS:
            raise CallError('Invalid disk format specified.', errno.ENOENT)

        # Grab the owner / group of the parent directory
        parent_stat = os.stat(data['directory'])
        owner = parent_stat.st_uid
        group = parent_stat.st_gid

        # Get the raw zvol device path
        zvol_device_path = str(zvol_name_to_path(data['zvol']))

        # Set the target file location
        zvolbasename = os.path.basename(data['zvol'])
        targetfile = f"{data['directory']}/vmdisk-{zvolbasename}.{format}"

        # Use quotes safely and assemble the command
        filesafe = shlex.quote(targetfile)
        devsafe = shlex.quote(zvol_device_path)
        command = f"qemu-img convert -p -f raw -O {data['format']} {devsafe} {filesafe}"
        self.logger.warning('Running Disk export using: "' + command + '"')

        cp = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)

        re_progress = re.compile(r'(\d+\.\d+)')
        stderr = ''

        for line in iter(cp.stdout.readline, ""):
            progress = re_progress.search(line.lstrip())
            if progress:
                try:
                    progress = round(float(progress.group(1)))
                    job.set_progress(progress, "Disk Export Progress")
                except ValueError:
                    self.logger.warning('Invalid progress in: "' + progress.group(1) + '"')
            else:
                stderr += line
                self.logger.warning('No progress reported from qemu-img: "' + line.lstrip() + '"')
        cp.wait()

        if cp.returncode:
            raise CallError(f'Failed to export disk: {stderr}')

        # Set the owner / group of the target file to inherit that of the saved parent directory
        os.chown(targetfile, owner, group)

        return True
