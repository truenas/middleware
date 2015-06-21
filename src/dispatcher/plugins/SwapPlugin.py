#+
# Copyright 2014 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

import os
import re
import logging
from task import Provider
from lib.system import system
from lib.geom import confxml


logger = logging.getLogger('SwapPlugin')


class SwapProvider(Provider):
    def info(self):
        return get_swap_info(self.dispatcher)


def get_available_disks(dispatcher):
    disks = []
    for i in dispatcher.call_sync('volumes.query'):
        disks += dispatcher.call_sync('volumes.get_volume_disks', i['name'])

    return disks


def get_swap_partition(dispatcher, disk):
    disk = dispatcher.call_sync('disks.query', [('path', '=', disk)], {'single': True})
    if not disk:
        return None

    return disk['status'].get('swap-partition-path')


def get_swap_info(dispatcher):
    xml = confxml()
    result = {}

    for mirror in xml.xpath("/mesh/class[name='MIRROR']/geom"):
        name = mirror.find('name').text
        if not re.match(r'^swap\d+$', name):
            continue

        swap = {
            'name': name,
            'disks': []
        }

        for cons in mirror.findall('consumer'):
            prov = cons.find('provider').attrib['ref']
            prov = xml.xpath(".//provider[@id='{0}']".format(prov))[0]
            disk_geom = prov.find('geom').attrib['ref']
            disk_geom = xml.xpath(".//geom[@id='{0}']".format(disk_geom))[0]
            swap['disks'].append(os.path.join('/dev', disk_geom.find('name').text))

        result[name] = swap

    return result


def clear_swap(dispatcher):
    logger.info('Clearing all swap mirrors in system')
    for swap in get_swap_info(dispatcher).values():
        logger.debug('Clearing swap mirror %s', swap['name'])
        system('/sbin/swapoff', os.path.join('/dev/mirror', swap['name']))
        system('/sbin/gmirror', 'destroy', swap['name'])


def remove_swap(dispatcher, disks):
    disks = set(disks)
    for swap in get_swap_info(dispatcher).values():
        if disks & set(swap['disks']):
            system('/sbin/swapoff', os.path.join('/dev/mirror', swap['name']))
            system('/sbin/gmirror', 'destroy', swap['name'])

    # Try to create new swap partitions, as at this stage we
    # might have two unused data disks
    if len(disks) > 0:
        rearrange_swap(dispatcher)


def create_swap(dispatcher, disks):
    disks = filter(lambda x: x is not None, map(lambda x: get_swap_partition(dispatcher, x), disks))
    for idx, pair in enumerate(zip(*[iter(disks)] * 2)):
        name = 'swap{0}'.format(idx)q
        disk_a, disk_b = pair
        logger.info('Creating swap partition %s from disks: %s, %s', name, disk_a, disk_b)
        system('/sbin/gmirror', 'label', '-b', 'prefer', name, disk_a, disk_b)
        system('/sbin/swapon', '/dev/mirror/{0}'.format(name))


def rearrange_swap(dispatcher):
    swap_info = get_swap_info(dispatcher).values()
    swap_disks = set(get_available_disks(dispatcher))
    active_swap_disks = set(sum(map(lambda s: s['disks'], swap_info), []))

    logger.debug('Rescanning available disks')
    logger.debug('Disks already used for swap: %s', ', '.join(active_swap_disks))
    logger.debug('Disks that could be used for swap: %s', ', '.join(swap_disks - active_swap_disks))
    logger.debug('Disks that can\'t be used for swap anymore: %s', ', '.join(active_swap_disks - swap_disks))

    create_swap(dispatcher, list(swap_disks - active_swap_disks))
    remove_swap(dispatcher, list(active_swap_disks - swap_disks))


def _depends():
    return ['VolumePlugin']


def _init(dispatcher, plugin):
    def volumes_pre_detach(args):
        disks = dispatcher.call_sync('volumes.get_volume_disks', args['name'])
        remove_swap(dispatcher, disks)

    def on_volumes_change(args):
        rearrange_swap(dispatcher)

    plugin.register_provider('swap', SwapProvider)
    plugin.register_event_handler('volumes.changed', on_volumes_change)
    plugin.attach_hook('volumes.pre-destroy', volumes_pre_detach)
    plugin.attach_hook('volumes.pre-detach', volumes_pre_detach)

    clear_swap(dispatcher)
    rearrange_swap(dispatcher)
