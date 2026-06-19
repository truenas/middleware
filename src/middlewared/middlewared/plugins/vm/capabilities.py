import functools
import re
import subprocess

from middlewared.service import ServiceContext

from .constants import VMGuestArch

RE_MACHINE_TYPE_CHOICES = re.compile(r'^\s*(?!none\s)(\S+)(?=\s{2,})', flags=re.M)


def get_capabilities(context: ServiceContext) -> dict[str, list[str]]:
    supported_archs = {}

    cp = subprocess.run(['/usr/bin/qemu-system-x86_64', '-machine', 'help'], capture_output=True, text=True)
    if cp.returncode:
        context.logger.warning(f'Failed to query machine types for {VMGuestArch.X86_64}: {cp.stderr}')
    else:
        if machine_types := RE_MACHINE_TYPE_CHOICES.findall(cp.stdout):
            supported_archs[VMGuestArch.X86_64] = machine_types

    cp = subprocess.run(['/usr/bin/qemu-system-i386', '-machine', 'help'], capture_output=True, text=True)
    if cp.returncode:
        context.logger.warning(f'Failed to query machine types for {VMGuestArch.I686}: {cp.stderr}')
    else:
        if machine_types := RE_MACHINE_TYPE_CHOICES.findall(cp.stdout):
            supported_archs[VMGuestArch.I686] = machine_types

    # qemu-system-aarch64 reports ~100 machine types: virt*/sbsa-ref plus many
    # real boards (raspi*, vexpress*, sabrelite, xlnx-*) and microcontroller
    # platforms (cortex-m*, mps2/mps3-an*, microbit, netduino*). We surface
    # everything for parity with the x86 path -- frontend can group/filter if
    # the dropdown gets unwieldy. Revisit if real users are picking unbootable
    # microcontroller machines and filing bugs.
    cp = subprocess.run(['/usr/bin/qemu-system-aarch64', '-machine', 'help'], capture_output=True, text=True)
    if cp.returncode:
        context.logger.warning(f'Failed to query machine types for {VMGuestArch.AARCH64}: {cp.stderr}')
    else:
        if machine_types := RE_MACHINE_TYPE_CHOICES.findall(cp.stdout):
            supported_archs[VMGuestArch.AARCH64] = machine_types

    return supported_archs


@functools.cache
def guest_architecture_and_machine_choices(context: ServiceContext) -> dict[str, list[str]]:
    return get_capabilities(context)
