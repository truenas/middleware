import binascii
import contextlib
import ctypes
import glob
import ipaddress
import os
import os.path
import pathlib
import socket
import subprocess

from middlewared.service import Service


class sockaddr_in(ctypes.Structure):
    _fields_ = [('sa_family', ctypes.c_ushort),  # sin_family
                ('sin_port', ctypes.c_ushort),
                ('sin_addr', ctypes.c_byte * 4),
                ('__pad', ctypes.c_byte * 8)]    # struct sockaddr_in is 16 bytes


def to_sockaddr(address, port=None):
    addr_obj = ipaddress.ip_address(address)
    if addr_obj.version == 4:
        addr = sockaddr_in()
        addr.sa_family = ctypes.c_ushort(socket.AF_INET)
        if port:
            addr.sin_port = ctypes.c_ushort(socket.htons(port))
        if address:
            bytes_ = [int(i) for i in address.split('.')]
            addr.sin_addr = (ctypes.c_byte * 4)(*bytes_)
    else:
        raise NotImplementedError('Not implemented')

    return addr


class KernelDistributedLockManagerService(Service):
    """
    Simple synchronous interface with the kernel dlm.
    """
    class Config:
        private = True
        namespace = 'dlm.kernel'

    SYSFS_DIR = '/sys/kernel/dlm'
    CLUSTER_DIR = '/sys/kernel/config/dlm/cluster'
    SPACES_DIR = CLUSTER_DIR + '/spaces'
    COMMS_DIR = CLUSTER_DIR + '/comms'
    CLUSTER_NAME = "HA"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopped = {}

    def load_kernel_module(self, name="HA"):
        if not os.path.isdir(KernelDistributedLockManagerService.SYSFS_DIR):
            self.logger.info('Loading kernel dlm')
            try:
                subprocess.run(["modprobe", "dlm"])
            except subprocess.CalledProcessError as e:
                self.logger.error('Failed to load dlm kernel module. Error %r', e)
        for d in (KernelDistributedLockManagerService.CLUSTER_DIR,
                  KernelDistributedLockManagerService.SPACES_DIR,
                  KernelDistributedLockManagerService.COMMS_DIR):
            with contextlib.suppress(FileExistsError):
                os.mkdir(d)
                if d == KernelDistributedLockManagerService.CLUSTER_DIR:
                    with open(f'{d}/cluster_name', 'w') as f:
                        f.write(name)

    def comms_add_node(self, nodeid, addr, local, port=0, mark=None):
        # Create comms directory for this node if necessary
        node_path = os.path.join(KernelDistributedLockManagerService.COMMS_DIR, str(nodeid))
        with contextlib.suppress(FileExistsError):
            os.mkdir(node_path)

            # Set the nodeid
            with open(os.path.join(node_path, 'nodeid'), 'w') as f:
                f.write(str(nodeid))

            # Set the address
            sockbytes = bytes(to_sockaddr(addr, port))
            data = sockbytes + bytes(128 - len(sockbytes))
            with open(os.path.join(node_path, 'addr'), 'wb') as f:
                f.write(data)

            # Set skb mark.
            # Added to kernel 5.9 in a5b7ab6352bf ("fs: dlm: set skb mark for listen socket")
            if mark is not None:
                with open(os.path.join(node_path, 'mark'), 'w') as f:
                    f.write(str(mark))

            # Finally set whether local or not
            with open(os.path.join(node_path, 'local'), 'w') as f:
                f.write('1' if local else '0')

    def comms_remove_node(self, nodeid):
        node_path = os.path.join(KernelDistributedLockManagerService.COMMS_DIR, str(nodeid))
        with contextlib.suppress(FileNotFoundError):
            os.rmdir(node_path)

    def comms_node_ready(self, nodeid):
        p = pathlib.Path(KernelDistributedLockManagerService.COMMS_DIR, str(nodeid))
        return p.is_dir()

    def set_sysfs(self, section, attribute, value):
        with open(os.path.join(KernelDistributedLockManagerService.SYSFS_DIR, section, attribute), 'w') as f:
            f.write(str(value))

    def set_sysfs_control(self, lockspace_name, value):
        self.set_sysfs(lockspace_name, 'control', value)

    def set_sysfs_event_done(self, lockspace_name, value):
        self.logger.debug('Event done lockspace %s value %s', lockspace_name, value)
        self.set_sysfs(lockspace_name, 'event_done', value)

    def set_sysfs_id(self, lockspace_name, value):
        self.set_sysfs(lockspace_name, 'id', value)

    def set_sysfs_nodir(self, lockspace_name, value):
        self.set_sysfs(lockspace_name, 'nodir', value)

    def lockspace_set_global_id(self, lockspace_name):
        self.logger.debug('Setting global id for lockspace %s', lockspace_name)
        self.set_sysfs_id(lockspace_name, binascii.crc32(f'dlm:ls:{lockspace_name}\00'.encode('utf-8')))

    def lockspace_present(self, lockspace_name):
        return os.path.isdir(os.path.join(KernelDistributedLockManagerService.SYSFS_DIR, lockspace_name))

    def lockspace_mark_stopped(self, lockspace_name):
        self.stopped[lockspace_name] = True

    def lockspace_is_stopped(self, lockspace_name):
        return self.stopped.get(lockspace_name, False)

    def lockspace_stop(self, lockspace_name):
        if not self.stopped.get(lockspace_name, False):
            self.set_sysfs_control(lockspace_name, 0)
            self.stopped[lockspace_name] = True
            self.logger.debug('Stopped lockspace %s', lockspace_name)
            return True
        else:
            return False

    def lockspace_start(self, lockspace_name):
        if self.stopped.get(lockspace_name, False):
            self.set_sysfs_control(lockspace_name, 1)
            self.stopped[lockspace_name] = False
            self.logger.debug('Started lockspace %s', lockspace_name)
            return True
        else:
            return False

    def lockspace_add_node(self, lockspace_name, nodeid, weight=None):
        """
        Add the specified node to the lockspace
        """
        self.logger.debug('Adding node %s to lockspace %s', nodeid, lockspace_name)
        spaces_path = os.path.join(KernelDistributedLockManagerService.SPACES_DIR, lockspace_name)
        with contextlib.suppress(FileExistsError):
            os.mkdir(spaces_path)
        # Check to see if we already have the directory, and remove it if so
        # so dlm-kernel can notice they've left and rejoined.
        node_path = os.path.join(spaces_path, 'nodes', '%d' % nodeid)
        with contextlib.suppress(FileNotFoundError):
            os.rmdir(node_path)
        with contextlib.suppress(FileExistsError):
            os.mkdir(node_path)
            with open(os.path.join(node_path, 'nodeid'), 'w') as f:
                f.write(str(nodeid))
            if weight is not None:
                with open(os.path.join(node_path, 'weight'), 'w') as f:
                    f.write(str(weight))

    def lockspace_remove_node(self, lockspace_name, nodeid):
        """
        Remove the specified nodeid from the lockspace.
        """
        self.logger.debug('Removing node %s from lockspace %s', nodeid, lockspace_name)
        node_path = os.path.join(KernelDistributedLockManagerService.SPACES_DIR, lockspace_name, 'nodes', '%d' % nodeid)
        with contextlib.suppress(FileNotFoundError):
            os.rmdir(node_path)

    def lockspace_leave(self, lockspace_name):
        """
        Current node is leaving the lockspace.

        Remove all nodes and delete the lockspace.
        """
        self.logger.debug('Leaving lockspace %s', lockspace_name)
        spaces_path = os.path.join(KernelDistributedLockManagerService.SPACES_DIR, lockspace_name)
        with contextlib.suppress(FileNotFoundError):
            for d in glob.glob(os.path.join(spaces_path, 'nodes', '*')):
                os.rmdir(d)
            os.rmdir(spaces_path)
        if lockspace_name in self.stopped:
            del self.stopped[lockspace_name]

    def destroy(self):
        with contextlib.suppress(FileNotFoundError):
            for dirname in glob.glob(os.path.join(KernelDistributedLockManagerService.COMMS_DIR, '*')):
                os.rmdir(dirname)
            for dirname in glob.glob(os.path.join(KernelDistributedLockManagerService.SPACES_DIR, '*')):
                os.rmdir(dirname)
            os.rmdir(KernelDistributedLockManagerService.CLUSTER_DIR)

    def node_lockspaces(self, nodeid):
        """
        Return an iterator that will yield the names of the lockspaces that contain
        the specified nodeid.
        """
        p = pathlib.Path(KernelDistributedLockManagerService.SPACES_DIR)
        for lsnp in p.glob(f'*/nodes/{nodeid}'):
            yield lsnp.parts[-3]
