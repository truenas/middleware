# import pytest

from truenas_api_client import Client


def test_hardware_variant():
    """This test supports running under KVM, Hyper-v, VirtualBox and real hardware"""
    with Client() as c:
        variant = c.call('hardware.virtualization.variant')
        assert variant in ['kvm', 'microsoft', 'oracle', 'none']
