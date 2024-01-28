import shlex

from middlewared.plugins.vm.devices import CDROM, DISK, PCI, RAW, DISPLAY, USB
from middlewared.plugins.vm.numeric_set import parse_numeric_set
from middlewared.utils import Nid

from .utils import create_element


def domain_children(vm_data, context):
    children = [
        create_element('name', attribute_dict={'text': f'{vm_data["id"]}_{vm_data["name"]}'}),
        create_element('uuid', attribute_dict={'text': vm_data['uuid']}),
        create_element('title', attribute_dict={'text': vm_data['name']}),
        create_element('description', attribute_dict={'text': vm_data['description']}),
        # OS/boot related xml - returns an iterable
        os_xml(vm_data),
        # CPU related xml
        *cpu_xml(vm_data, context),
        # Memory related xml
        *memory_xml(vm_data),
        # Add features
        features_xml(vm_data),
        # Clock offset
        clock_xml(vm_data),
        # Command line args
        commandline_xml(vm_data),
        # Devices
        devices_xml(vm_data, context),
    ]

    # Wire memory if PCI passthru device is configured
    #   Implicit configuration for now.
    #
    #   To avoid surprising side effects from implicit configuration, wiring of memory
    #   should preferably be an explicit vm configuration option and trigger error
    #   message if not selected when PCI passthru is configured.
    #
    if any(isinstance(device, PCI) for device in context['devices']):
        children.append(
            create_element(
                'memoryBacking', attribute_dict={
                    'children': [
                        create_element('locked'),
                    ]
                }
            )
        )

    return children


def clock_xml(vm_data):
    timers = []
    if vm_data['hyperv_enlightenments']:
        timers = [create_element('timer', name='hypervclock', present='yes')]

    return create_element(
        'clock', attribute_dict={'children': timers},
        offset='localtime' if vm_data['time'] == 'LOCAL' else 'utc'
    )


def commandline_xml(vm_data):
    return create_element(
        'commandline', xmlns='http://libvirt.org/schemas/domain/qemu/1.0', attribute_dict={
            'children': [create_element('arg', value=arg) for arg in shlex.split(vm_data['command_line_args'])]
        }
    )


def cpu_xml(vm_data, context):
    features = []
    if vm_data['cpu_mode'] == 'HOST-PASSTHROUGH':
        features.append(create_element('cache', mode='passthrough'))

    cpu_nodes = [
        create_element(
            'cpu', attribute_dict={
                'children': [
                    create_element(
                        'topology', sockets=str(vm_data['vcpus']), cores=str(vm_data['cores']),
                        threads=str(vm_data['threads'])
                    ),
                ] + ([
                    create_element(
                        'model', fallback='forbid', attribute_dict={'text': vm_data['cpu_model']}
                    )
                    # Right now this is best effort for the domain to start with specified CPU Model and not fallback
                    # However if some features are missing in the host, qemu will right now still start the domain
                    # and mark them as missing. We should perhaps make this configurable in the future to control
                    # if domain should/should not be started
                ] if vm_data['cpu_mode'] == 'CUSTOM' and vm_data['cpu_model'] and context['cpu_model_choices'].get(
                    vm_data['cpu_model']
                ) else []) + features,
            }, mode=vm_data['cpu_mode'].lower(),
        ),
        # VCPU related xml
        create_element(
            'vcpu',
            attribute_dict={
                'text': str(vm_data['vcpus'] * vm_data['cores'] * vm_data['threads']),
            }, **({'cpuset': vm_data['cpuset']} if vm_data['cpuset'] else {}),
        )
    ]

    if vm_data['pin_vcpus'] and vm_data['cpuset']:
        cpu_nodes.append(create_element('cputune', attribute_dict={
            'children': [
                create_element('vcpupin', vcpu=str(i), cpuset=str(cpu))
                for i, cpu in enumerate(parse_numeric_set(vm_data['cpuset']))
            ]
        }))

    if vm_data['nodeset']:
        cpu_nodes.append(create_element(
            'numatune', attribute_dict={
                'children': [
                    create_element('memory', nodeset=vm_data['nodeset']),
                ]
            },
        ))

    return cpu_nodes


def devices_xml(vm_data, context):
    boot_no = Nid(1)
    scsi_device_no = Nid(1)
    usb_controller_no = Nid(1)
    # nec-xhci is added by default for each domain by libvirt so we update our mapping accordingly
    usb_controllers = {'nec-xhci': 0}
    virtual_device_no = Nid(1)
    devices = []
    for device in context['devices']:
        if isinstance(device, (DISK, CDROM, RAW)):
            if device.data['attributes'].get('type') == 'VIRTIO':
                disk_no = virtual_device_no()
            else:
                disk_no = scsi_device_no()
            device_xml = device.xml(disk_number=disk_no, boot_number=boot_no())
        elif isinstance(device, USB):
            device_xml = []
            if device.controller_type not in usb_controllers:
                usb_controllers[device.controller_type] = usb_controller_no()
                device_xml.append(create_element(
                    'controller', type='usb', index=str(usb_controllers[device.controller_type]),
                    model=device.controller_type)
                )
            usb_device_xml = device.xml(controller_mapping=usb_controllers)
            if isinstance(usb_device_xml, (tuple, list)):
                device_xml.extend(usb_device_xml)
            else:
                device_xml.append(usb_device_xml)
        else:
            device_xml = device.xml()
        devices.extend(device_xml if isinstance(device_xml, (tuple, list)) else [device_xml])

    spice_server_available = display_device_available = False
    for device in filter(lambda d: isinstance(d, DISPLAY), context['devices']):
        display_device_available = True
        if device.is_spice_type():
            spice_server_available = True
            break

    if vm_data['ensure_display_device'] and not display_device_available:
        # We should add a video device if there is no display device configured because most by
        # default if not all headless servers like ubuntu etc require it to boot
        devices.append(create_element('video'))

    if spice_server_available:
        # We always add spicevmc channel device when a spice display device is available to allow users
        # to install guest agents for improved vm experience
        devices.append(create_element(
            'channel', type='spicevmc', attribute_dict={
                'children': [create_element('target', type='virtio', name='com.redhat.spice.0')]
            }
        ))

    if vm_data['trusted_platform_module']:
        devices.append(create_element(
            'tpm', model='tpm-crb', attribute_dict={
                'children': [create_element('backend', type='emulator', version='2.0')]
            },
        ))

    devices.append(create_element('channel', type='unix', attribute_dict={
        'children': [create_element('target', type='virtio', name='org.qemu.guest_agent.0')]
    }))
    devices.append(create_element('serial', type='pty'))
    if vm_data['min_memory']:
        # memballoon device needs to be added if memory ballooning is enabled
        devices.append(create_element('memballoon', model='virtio', autodeflate='on'))
    return create_element('devices', attribute_dict={'children': devices})


def features_xml(vm_data):
    features = []
    if vm_data['hide_from_msr']:
        features.append(
            create_element('kvm', attribute_dict={'children': [create_element('hidden', state='on')]})
        )

    if vm_data['hyperv_enlightenments']:
        features.append(get_hyperv_xml())

    return create_element(
        'features', attribute_dict={
            'children': [
                create_element('acpi'),
                create_element('apic'),
                create_element('msrs', unknown='ignore'),
            ] + features,
        }
    )


# Documentation for each enlightenment can be found from:
# https://github.com/qemu/qemu/blob/master/docs/system/i386/hyperv.rst
def get_hyperv_xml():
    return create_element(
        'hyperv', attribute_dict={
            'children': [
                create_element('relaxed', state='on'),
                create_element('vapic', state='on'),
                create_element('spinlocks', state='on', retries='8191'),
                create_element('reset', state='on'),
                create_element('frequencies', state='on'),
                # All enlightenments under vpindex depend on it.
                create_element('vpindex', state='on'),
                create_element('synic', state='on'),
                create_element('ipi', state='on'),
                create_element('tlbflush', state='on'),
                create_element('stimer', state='on')
            ],
        }
    )


def memory_xml(vm_data):
    memory_xml_nodes = [create_element('memory', unit='M', attribute_dict={'text': str(vm_data['memory'])})]
    # Memory Ballooning - this will be memory which will always be allocated to the VM
    # If not specified, this defaults to `memory`
    if vm_data['min_memory']:
        memory_xml_nodes.append(
            create_element('currentMemory', unit='M', attribute_dict={'text': str(vm_data['min_memory'])})
        )
    return memory_xml_nodes


def os_xml(vm_data):
    children = [create_element(
        'type',
        attribute_dict={'text': 'hvm'}, **{
            k[:-5]: vm_data[k] for k in filter(lambda t: vm_data[t], ('arch_type', 'machine_type'))
        }
    )]
    if vm_data['bootloader'] == 'UEFI':
        children.append(
            create_element(
                'loader', attribute_dict={'text': f'/usr/share/OVMF/{vm_data["bootloader_ovmf"]}'},
                readonly='yes', type='pflash',
            ),
        )
    if vm_data['nvram_location']:
        children.append(create_element('nvram', attribute_dict={'text': vm_data['nvram_location']}))
    return create_element('os', attribute_dict={'children': children})
