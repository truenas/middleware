import errno
import os
import subprocess

from middlewared.plugins.zfs_.utils import zvol_name_to_path
from middlewared.schema import accepts, Bool, returns, Str
from middlewared.service import CallError, Service

class VMService(Service):

    @accepts(
        Str('diskimg', default=None),
        Str('zvol', default=None)
    )
    @returns(Bool())
    async def import_disk_image(self, diskimg, zvol):
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
        
        if diskimg == None:
           self.logger.error('Missing disk image') 
           return False
        if zvol == None:
           self.logger.error('Missing zvol parameter')
           return False
        if not await self.middleware.call('zfs.dataset.query', [('id', '=', zvol)]):
           raise CallError(f'zvol {zvol} does not exist.', errno.ENOENT)

        if os.path.exists(diskimg) == False:
           self.logger.error('Disk Image does not exist')
           return False

        if os.path.exists(zvol_name_to_path(zvol)) == False:
           self.logger.error('zvol device does not exist')
           return False

        zvol_device_path = str(zvol_name_to_path(zvol))

        command = "qemu-img convert -p -O raw " + diskimg + " " + zvol_device_path
        self.logger.warning('Running Disk Import using: "' + command + '"')

        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)

        for line in process.stdout:
            # Display output
            self.logger.warning(line.strip)

        process.wait()

        # Report any failure
        if process.returncode != 0:
            for line in process.stderr:
                # Display output
                self.logger.warning(line.strip)
            self.logger.error('Failed importing disk image')
            return False

        return True
