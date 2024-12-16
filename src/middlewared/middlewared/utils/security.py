import enum


class STIGType(enum.IntFlag):
    """
    Currently we are only attempting to meet a single STIG (General Purpose
    Operating System). This enum is defined so that we have capability
    to expand if we decide to apply more specific STIGs to different areas
    of our product
    """
    # https://www.stigviewer.com/stig/general_purpose_operating_system_srg/
    GPOS = enum.auto()  # General Purpose Operating System


def system_security_config_to_stig_type(config: dict[str, bool]) -> STIGType:
    return STIGType.GPOS if config['enable_gpos_stig'] else 0
