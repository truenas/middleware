import functools
import os.path
import enum
import re

import libvirt

from middlewared.plugins.vm.utils import create_element  # noqa


OVMF_DIR = '/usr/share/OVMF'


class DomainState(enum.Enum):
    NOSTATE = libvirt.VIR_DOMAIN_NOSTATE
    RUNNING = libvirt.VIR_DOMAIN_RUNNING
    BLOCKED = libvirt.VIR_DOMAIN_BLOCKED
    PAUSED = libvirt.VIR_DOMAIN_PAUSED
    SHUTDOWN = libvirt.VIR_DOMAIN_SHUTDOWN
    SHUTOFF = libvirt.VIR_DOMAIN_SHUTOFF
    CRASHED = libvirt.VIR_DOMAIN_CRASHED
    PMSUSPENDED = libvirt.VIR_DOMAIN_PMSUSPENDED


@functools.cache
def get_ovmf_vars_file(code_filename: str, ovmf_dir: str = OVMF_DIR) -> str | None:
    """
    Given an OVMF CODE filename, return the matching VARS file path.

    Matching is done based on:
    - Size variant (e.g., _4M must match)
    - Secure boot support (secboot/ms CODE files get .ms VARS)
    - Special variants like snakeoil get their matching VARS

    Args:
        code_filename: The OVMF CODE filename (e.g., 'OVMF_CODE.secboot.fd')
        ovmf_dir: Directory containing OVMF files (default: /usr/share/OVMF)

    Returns:
        Full path to matching VARS file, or None if no match found
    """
    basename = os.path.basename(code_filename)

    if not basename.startswith('OVMF_CODE'):
        return None

    # Extract size variant (e.g., '_4M')
    size_match = re.search(r'(_\d+M)', basename)
    size_variant = size_match.group(1) if size_match else ''

    # Check for secure boot indicators
    is_secboot = any(indicator in basename for indicator in ['.secboot', '.ms'])

    # Check for snakeoil (self-signed test keys)
    is_snakeoil = '.snakeoil' in basename

    # Build candidate VARS filenames in order of preference
    candidates = []

    if is_snakeoil:
        candidates.append(f'OVMF_VARS{size_variant}.snakeoil.fd')
        candidates.append(f'OVMF_VARS{size_variant}.ms.fd')
    elif is_secboot:
        candidates.append(f'OVMF_VARS{size_variant}.ms.fd')

    # Always add the basic variant as fallback
    candidates.append(f'OVMF_VARS{size_variant}.fd')

    # Find first existing candidate
    for candidate in candidates:
        candidate_path = os.path.join(ovmf_dir, candidate)
        if os.path.exists(candidate_path):
            return candidate_path

    return None
