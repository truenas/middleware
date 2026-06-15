import functools
import re
import subprocess

from middlewared.service import ServiceContext

RE_MACHINE_TYPE_CHOICES = re.compile(r'^\s*(?!none\s)(\S+)(?=\s{2,})', flags=re.M)


def get_capabilities(context: ServiceContext) -> dict[str, list[str]]:
    supported_archs = {}

    cp = subprocess.run(['/usr/bin/qemu-system-x86_64', '-machine', 'help'], capture_output=True, text=True)
    if cp.returncode:
        context.logger.warning(f'Failed to query machine types for x86_64: {cp.stderr}')
    else:
        if machine_types := RE_MACHINE_TYPE_CHOICES.findall(cp.stdout):
            supported_archs['x86_64'] = machine_types

    cp = subprocess.run(['/usr/bin/qemu-system-i386', '-machine', 'help'], capture_output=True, text=True)
    if cp.returncode:
        context.logger.warning(f'Failed to query machine types for i686: {cp.stderr}')
    else:
        if machine_types := RE_MACHINE_TYPE_CHOICES.findall(cp.stdout):
            supported_archs['i686'] = machine_types

    # qemu-system-aarch64 reports ~100 machine types: virt*/sbsa-ref plus many
    # real boards (raspi*, vexpress*, sabrelite, xlnx-*) and microcontroller
    # platforms (cortex-m*, mps2/mps3-an*, microbit, netduino*). We surface
    # everything for parity with the x86 path -- frontend can group/filter if
    # the dropdown gets unwieldy. Revisit if real users are picking unbootable
    # microcontroller machines and filing bugs.
    cp = subprocess.run(['/usr/bin/qemu-system-aarch64', '-machine', 'help'], capture_output=True, text=True)
    if cp.returncode:
        context.logger.warning(f'Failed to query machine types for aarch64: {cp.stderr}')
    else:
        if machine_types := RE_MACHINE_TYPE_CHOICES.findall(cp.stdout):
            supported_archs['aarch64'] = machine_types

    return supported_archs


@functools.cache
def guest_architecture_and_machine_choices(context: ServiceContext) -> dict[str, list[str]]:
    return get_capabilities(context)
