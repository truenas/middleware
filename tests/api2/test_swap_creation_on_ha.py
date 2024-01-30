#!/usr/bin/env python3
import pytest
import os
import sys

apifolder = os.getcwd()
sys.path.append(apifolder)

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call
from auto_config import ha


if ha:
    @pytest.mark.disk
    def test_swap_creation_on_ha(request):
        with another_pool():
            swap_disks = [
                provider['disk']
                for swap_mirror in call('disk.get_swap_mirrors') for provider in swap_mirror['providers']
            ]
            pool_disks = call('pool.get_disks')
            assert all(disk not in swap_disks for disk in pool_disks) is True, 'Pool disks ' \
                                                                               f'({", ".join(pool_disks)!r}) should ' \
                                                                               'not be used for swap ( swap disks: ' \
                                                                               f'{", ".join(swap_disks)} )'
