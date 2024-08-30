import pytest

from xml.etree import ElementTree as etree

from middlewared.plugins.vm.supervisor.domain_xml import clock_xml, commandline_xml, cpu_xml, features_xml


@pytest.mark.parametrize('vm_data,expected_xml', [
    ({'hyperv_enlightenments': False, 'time': 'LOCAL'}, '<clock offset="localtime" />'),
    ({'hyperv_enlightenments': True, 'time': 'LOCAL'},
     '<clock offset="localtime"><timer name="hypervclock" present="yes" /></clock>'),
    ({'hyperv_enlightenments': True, 'time': 'UTC'},
     '<clock offset="utc"><timer name="hypervclock" present="yes" /></clock>'),
])
def test_clock_xml(vm_data, expected_xml):
    assert etree.tostring(clock_xml(vm_data)).decode().strip() == expected_xml


@pytest.mark.parametrize('vm_data,expected_xml', [
    ({'command_line_args': ''}, '<commandline xmlns="http://libvirt.org/schemas/domain/qemu/1.0" />'),
    ({'command_line_args': '-set group.id.arg=value'},
     '<commandline xmlns="http://libvirt.org/schemas/domain/qemu/1.0"><arg value="-set" />'
     '<arg value="group.id.arg=value" /></commandline>'),
])
def test_command_line_xml(vm_data, expected_xml):
    assert etree.tostring(commandline_xml(vm_data)).decode().strip() == expected_xml


@pytest.mark.parametrize('vm_data,context,expected_xml', [
    ({
        'cpu_mode': 'CUSTOM',
        'vcpus': 1,
        'cores': 2,
        'threads': 3,
        'cpu_model': None,
        'cpuset': None,
        'pin_vcpus': False,
        'nodeset': None,
        'enable_cpu_topology_extension': False
    }, {'cpu_model_choices': {}}, [
        '<cpu mode="custom"><topology sockets="1" cores="2" threads="3" /></cpu>',
        '<vcpu>6</vcpu>',
    ]),
    ({
        'cpu_mode': 'HOST-PASSTHROUGH',
        'vcpus': 1,
        'cores': 2,
        'threads': 3,
        'cpu_model': None,
        'cpuset': None,
        'pin_vcpus': False,
        'nodeset': None,
        'enable_cpu_topology_extension': False
    }, {'cpu_model_choices': {}}, [
        '<cpu mode="host-passthrough"><topology sockets="1" cores="2" threads="3" /><cache mode="passthrough" /></cpu>',
        '<vcpu>6</vcpu>',
    ]),
    ({
         'cpu_mode': 'HOST-PASSTHROUGH',
         'vcpus': 1,
         'cores': 2,
         'threads': 3,
         'cpu_model': None,
         'cpuset': None,
         'pin_vcpus': False,
         'nodeset': None,
         'enable_cpu_topology_extension': True
     }, {'cpu_model_choices': {}}, [
         '<cpu mode="host-passthrough"><topology sockets="1" cores="2" threads="3" />'
         '<cache mode="passthrough" /><feature policy="require" name="topoext" /></cpu>',
         '<vcpu>6</vcpu>',
     ]),
    ({
        'cpu_mode': 'CUSTOM',
        'vcpus': 1,
        'cores': 2,
        'threads': 3,
        'cpu_model': 'pentium',
        'cpuset': None,
        'pin_vcpus': False,
        'nodeset': None,
        'enable_cpu_topology_extension': False
    }, {'cpu_model_choices': {'pentium': 'pentium', 'pentium2': 'pentium2'}}, [
        '<cpu mode="custom"><topology sockets="1" cores="2" threads="3" />'
        '<model fallback="forbid">pentium</model></cpu>',
        '<vcpu>6</vcpu>',
    ]),
    ({
        'cpu_mode': 'CUSTOM',
        'vcpus': 1,
        'cores': 2,
        'threads': 3,
        'cpu_model': None,
        'cpuset': '1-2,4-6',
        'pin_vcpus': True,
        'nodeset': None,
        'enable_cpu_topology_extension': False,
    }, {'cpu_model_choices': {}}, [
        '<cpu mode="custom"><topology sockets="1" cores="2" threads="3" /></cpu>',
        '<vcpu cpuset="1-2,4-6">6</vcpu>',
        '<cputune><vcpupin vcpu="0" cpuset="1" /><vcpupin vcpu="1" cpuset="2" />'
        '<vcpupin vcpu="2" cpuset="4" /><vcpupin vcpu="3" cpuset="5" /><vcpupin vcpu="4" cpuset="6" /></cputune>',
    ]),
    ({
        'cpu_mode': 'CUSTOM',
        'vcpus': 1,
        'cores': 2,
        'threads': 3,
        'cpu_model': None,
        'cpuset': None,
        'pin_vcpus': False,
        'nodeset': '1-2,4-6',
        'enable_cpu_topology_extension': False
    }, {'cpu_model_choices': {}}, [
        '<cpu mode="custom"><topology sockets="1" cores="2" threads="3" /></cpu>',
        '<vcpu>6</vcpu>',
        '<numatune><memory nodeset="1-2,4-6" /></numatune>',
    ]),
])
def test_cpu_xml(vm_data, context, expected_xml):
    assert [etree.tostring(o).decode().strip() for o in cpu_xml(vm_data, context)] == expected_xml


@pytest.mark.parametrize('vm_data,expected_xml', [
    ({'hide_from_msr': False, 'hyperv_enlightenments': False},
     '<features><acpi /><apic /><msrs unknown="ignore" /></features>'),
    ({'hide_from_msr': True, 'hyperv_enlightenments': False},
     '<features><acpi /><apic /><msrs unknown="ignore" /><kvm><hidden state="on" /></kvm></features>'),
    ({'hide_from_msr': True, 'hyperv_enlightenments': True},
     '<features><acpi /><apic /><msrs unknown="ignore" /><kvm><hidden state="on" /></kvm>'
     '<hyperv><relaxed state="on" /><vapic state="on" /><spinlocks state="on" retries="8191" /><reset state="on" />'
     '<frequencies state="on" /><vpindex state="on" /><synic state="on" /><ipi state="on" /><tlbflush state="on" />'
     '<stimer state="on" /></hyperv></features>'),
])
def test_features_xml(vm_data, expected_xml):
    assert etree.tostring(features_xml(vm_data)).decode().strip() == expected_xml
