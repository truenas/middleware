import os


def render(service, middleware):
    os.makedirs('/run/truenas_libvirt', exist_ok=True)
