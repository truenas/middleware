import errno
import os
import re
import subprocess

from middlewared.plugins.zfs_.utils import zvol_name_to_path
from middlewared.schema import accepts, Bool, returns, Str
from middlewared.service import CallError, Service, job

class VMService(Service):

    @accepts(
        Str('diskimg', required=True),
        Str('zvol', required=True)
    )
    @returns(Bool())
    @job()
    def import_disk_image(self, job, diskimg, zvol):

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
        
        if not self.middleware.call_sync('zfs.dataset.query', [('id', '=', zvol)]):
           raise CallError(f'zvol {zvol} does not exist.', errno.ENOENT)

        if os.path.exists(diskimg) is False:
           raise CallError('Disk Image does not exist.', errno.ENOENT)

        if os.path.exists(zvol_name_to_path(zvol)) is False:
           raise CallError('Zvol device does not exist.', errno.ENOENT)

        zvol_device_path = str(zvol_name_to_path(zvol))

        command = "qemu-img convert -p -O raw " + diskimg + " " + zvol_device_path
        self.logger.warning('Running Disk Import using: "' + command + '"')

        cp = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)

        for line in iter(cp.stdout.readline, ""):
            progress = re.search(r'(\d+\.\d+)', line.lstrip())
            if progress:
                try:
                    progress = round(float(progress.group(1)))
                    progress_callback(progress, "Disk Import Progress")
                except ValueError:
                    self.logger.warning('Invalid progress in: "' + progress.group(1) + '"')
            else:
                self.logger.warning('No progress reported from qemu-img: "' + line.lstrip + '"')
        cp.wait()

        if cp.returncode:
            raise CallError(f'Failed to import disk: {stderr}')

        return True
