from xml.etree import ElementTree as etree


ACTIVE_STATES = ['RUNNING', 'SUSPENDED']
LIBVIRT_URI = 'qemu+unix:///system?socket=/run/truenas_libvirt/libvirt-sock'
LIBVIRT_USER = 'libvirt-qemu'
NGINX_PREFIX = '/vm/display'


def create_element(*args, **kwargs):
    attribute_dict = kwargs.pop('attribute_dict', {})
    element = etree.Element(*args, **kwargs)
    element.text = attribute_dict.get('text')
    element.tail = attribute_dict.get('tail')
    for child in attribute_dict.get('children', []):
        element.append(child)
    return element


def get_virsh_command_args():
    return ['virsh', '-c', LIBVIRT_URI]
