from middlewared.async_validators import check_path_resides_within_volume
from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.schema import accepts, Error, Int, Str, Dict, List, Bool, Patch
from middlewared.service import (
    item_method, pass_app, private, CRUDService, CallError, ValidationErrors, job
)
import middlewared.sqlalchemy as sa
from middlewared.utils import Nid, osc, Popen, run
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.utils.path import is_child
from middlewared.validators import Range, Match

import middlewared.logger
import asyncio
import contextlib
import errno
import enum
import functools
import ipaddress
import itertools
import libvirt
import math
try:
    import netif
except ImportError:
    netif = None
import os
import psutil
import random
import re
import stat
import shutil
import signal
import subprocess
import sys
try:
    import sysctl
except ImportError:
    sysctl = None
import time
import threading

from abc import ABC, abstractmethod
from lxml import etree

logger = middlewared.logger.Logger('vm').getLogger()

BUFSIZE = 65536

LIBVIRT_URI = 'bhyve+unix:///system'
LIBVIRT_AVAILABLE_SLOTS = 29  # 3 slots are being used by libvirt / bhyve


LIBVIRT_LOCK = asyncio.Lock()


ZVOL_CLONE_SUFFIX = '_clone'
ZVOL_CLONE_RE = re.compile(rf'^(.*){ZVOL_CLONE_SUFFIX}\d+$')


class VMService(CRUDService):

    async def __set_guest_vmemory(self, memory, overcommit):
        memory_available = await self.middleware.call('vm.get_available_memory', overcommit)
        memory_bytes = memory * 1024 * 1024
        if memory_bytes > memory_available:
            return False

        arc_max = sysctl.filter('vfs.zfs.arc.max')[0].value
        arc_min = sysctl.filter('vfs.zfs.arc.min')[0].value

        if arc_max > arc_min:
            new_arc_max = max(arc_min, arc_max - memory_bytes)
            self.logger.info(
                f'===> Setting ARC FROM: {arc_max} TO: {new_arc_max}'
            )
            sysctl.filter('vfs.zfs.arc.max')[0].value = new_arc_max
        return True

    @private
    async def init_guest_vmemory(self, vm, overcommit):
        guest_memory = vm.get('memory', None)
        guest_status = await self.middleware.call('vm.status', vm['id'])
        if guest_status.get('state') != 'RUNNING':
            setvmem = await self.__set_guest_vmemory(guest_memory, overcommit)
            if setvmem is False and not overcommit:
                raise CallError(f'Cannot guarantee memory for guest {vm["name"]}', errno.ENOMEM)
        else:
            raise CallError('bhyve process is running, we won\'t allocate memory')

    @private
    async def teardown_guest_vmemory(self, id):
        guest_status = await self.middleware.call('vm.status', id)
        if guest_status.get('state') != 'STOPPED':
            return

        vm = await self.middleware.call('datastore.query', 'vm.vm', [('id', '=', id)])
        guest_memory = vm[0].get('memory', 0) * 1024 * 1024
        arc_max = sysctl.filter('vfs.zfs.arc.max')[0].value
        arc_min = sysctl.filter('vfs.zfs.arc.min')[0].value
        new_arc_max = min(
            await self.middleware.call('vm.get_initial_arc_max'),
            arc_max + guest_memory
        )
        if arc_max != new_arc_max:
            if new_arc_max > arc_min:
                self.logger.debug(f'===> Give back guest memory to ARC: {new_arc_max}')
                sysctl.filter('vfs.zfs.arc.max')[0].value = new_arc_max
            else:
                self.logger.warn(
                    f'===> Not giving back memory to ARC because new arc_max ({new_arc_max}) <= arc_min ({arc_min})'
                )

    async def __next_clone_name(self, name):
        vm_names = [
            i['name']
            for i in await self.middleware.call('vm.query', [
                ('name', '~', rf'{name}{ZVOL_CLONE_SUFFIX}\d+')
            ])
        ]
        clone_index = 0
        while True:
            clone_name = f'{name}{ZVOL_CLONE_SUFFIX}{clone_index}'
            if clone_name not in vm_names:
                break
            clone_index += 1
        return clone_name

    async def __clone_zvol(self, name, zvol, created_snaps, created_clones):
        if not await self.middleware.call('zfs.dataset.query', [('id', '=', zvol)]):
            raise CallError(f'zvol {zvol} does not exist.', errno.ENOENT)

        snapshot_name = name
        i = 0
        while True:
            zvol_snapshot = f'{zvol}@{snapshot_name}'
            if await self.middleware.call('zfs.snapshot.query', [('id', '=', zvol_snapshot)]):
                if ZVOL_CLONE_RE.search(snapshot_name):
                    snapshot_name = ZVOL_CLONE_RE.sub(
                        rf'\1{ZVOL_CLONE_SUFFIX}{i}', snapshot_name,
                    )
                else:
                    snapshot_name = f'{name}{ZVOL_CLONE_SUFFIX}{i}'
                i += 1
                continue
            break

        await self.middleware.call('zfs.snapshot.create', {
            'dataset': zvol, 'name': snapshot_name,
        })
        created_snaps.append(zvol_snapshot)

        clone_suffix = name
        i = 0
        while True:
            clone_dst = f'{zvol}_{clone_suffix}'
            if await self.middleware.call('zfs.dataset.query', [('id', '=', clone_dst)]):
                if ZVOL_CLONE_RE.search(clone_suffix):
                    clone_suffix = ZVOL_CLONE_RE.sub(
                        rf'\1{ZVOL_CLONE_SUFFIX}{i}', clone_suffix,
                    )
                else:
                    clone_suffix = f'{name}{ZVOL_CLONE_SUFFIX}{i}'
                i += 1
                continue
            break

        if not await self.middleware.call('zfs.snapshot.clone', {
            'snapshot': zvol_snapshot, 'dataset_dst': clone_dst,
        }):
            raise CallError(f'Failed to clone {zvol_snapshot}.')

        created_clones.append(clone_dst)

        return clone_dst

    @item_method
    @accepts(Int('id'), Str('name', default=None))
    async def clone(self, id, name):
        """
        Clone the VM `id`.

        `name` is an optional parameter for the cloned VM.
        If not provided it will append the next number available to the VM name.
        """
        vm = await self.get_instance(id)

        origin_name = vm['name']
        del vm['id']
        del vm['status']

        vm['name'] = await self.__next_clone_name(vm['name'])

        if name is not None:
            vm['name'] = name

        # In case we need to rollback
        created_snaps = []
        created_clones = []
        try:
            for item in vm['devices']:
                item.pop('id', None)
                item.pop('vm', None)
                if item['dtype'] == 'NIC':
                    if 'mac' in item['attributes']:
                        del item['attributes']['mac']
                if item['dtype'] == 'VNC':
                    if 'vnc_port' in item['attributes']:
                        vnc_dict = await self.vnc_port_wizard()
                        item['attributes']['vnc_port'] = vnc_dict['vnc_port']
                if item['dtype'] == 'DISK':
                    zvol = item['attributes']['path'].replace('/dev/zvol/', '')
                    clone_dst = await self.__clone_zvol(
                        vm['name'], zvol, created_snaps, created_clones,
                    )
                    item['attributes']['path'] = f'/dev/zvol/{clone_dst}'
                if item['dtype'] == 'RAW':
                    item['attributes']['path'] = ''
                    self.logger.warn('For RAW disk you need copy it manually inside your NAS.')

            await self.do_create(vm)
        except Exception as e:
            for i in reversed(created_clones):
                try:
                    await self.middleware.call('zfs.dataset.delete', i)
                except Exception:
                    self.logger.warn('Rollback of VM clone left dangling zvol: %s', i)
            for i in reversed(created_snaps):
                try:
                    dataset, snap = i.split('@')
                    await self.middleware.call('zfs.snapshot.remove', {
                        'dataset': dataset,
                        'name': snap,
                        'defer_delete': True,
                    })
                except Exception:
                    self.logger.warn('Rollback of VM clone left dangling snapshot: %s', i)
            raise e
        self.logger.info('VM cloned from {0} to {1}'.format(origin_name, vm['name']))

        return True
