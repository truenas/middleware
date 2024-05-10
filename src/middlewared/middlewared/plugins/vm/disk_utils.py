import errno
import os
import re
import subprocess

from middlewared.plugins.zfs_.utils import zvol_name_to_path
from middlewared.schema import accepts, Bool, Dict, returns, Str
from middlewared.service import CallError, Service, job

# Valid Disk Formats we can export
VALID_DISK_FORMATS = ['qcow2', 'qed', 'raw', 'vdi', 'vpc', 'vmdk' ]

class VMService(Service):

    @accepts(Dict(
        'vm_info',
        Str('diskimg', required=True),
        Str('zvol', required=True)
    ))
    @returns(Bool())
    @job(lock_queue_size=1, lock=lambda args: f"import_disk_image_{args[-1]['zvol']}")
    def import_disk_image(self, job, data):

        def progress_callback(progress, description):
            job.set_progress(progress, description)

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

        command = f"qemu-img convert -p -O raw {data['diskimg']} {zvol_device_path}"
        self.logger.warning('Running Disk Import using: "' + command + '"')

        cp = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)

        re_progress = re.compile(r'(\d+\.\d+)')
        stderr = ''

        for line in iter(cp.stdout.readline, ""):
            progress = re_progress.search(line.lstrip())
            if progress:
                try:
                    progress = round(float(progress.group(1)))
                    progress_callback(progress, "Disk Import Progress")
                except ValueError:
                    self.logger.warning('Invalid progress in: "' + progress.group(1) + '"')
            else:
                stderr += line
                self.logger.warning('No progress reported from qemu-img: "' + line.lstrip() + '"')
        cp.wait()

        if cp.returncode:
            raise CallError(f'Failed to import disk: {stderr}')

        return True

    @accepts(Dict(
        'vm_info',
        Str('format', required=True),
        Str('directory', required=True),
        Str('zvol', required=True)
    ))
    @returns(Bool())
    @job(lock_queue_size=1, lock=lambda args: f"export_disk_image_{args[-1]['zvol']}")
    def export_disk_image(self, job, data):

        def progress_callback(progress, description):
            job.set_progress(progress, description)

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

        command = f"qemu-img convert -p -f raw -O {data['format']} {zvol_device_path} {targetfile}"
        self.logger.warning('Running Disk export using: "' + command + '"')

        cp = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)

        re_progress = re.compile(r'(\d+\.\d+)')
        stderr = ''

        for line in iter(cp.stdout.readline, ""):
            progress = re_progress.search(line.lstrip())
            if progress:
                try:
                    progress = round(float(progress.group(1)))
                    progress_callback(progress, "Disk Export Progress")
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
