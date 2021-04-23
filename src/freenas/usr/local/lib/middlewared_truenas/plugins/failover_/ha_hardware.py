import enum
import re


class HA_HARDWARE(enum.Enum):
    """
    The echostream E16 JBOD and the echostream Z-series chassis
    are the same piece of hardware. One of the only ways to differentiate
    them is to look at the enclosure elements in detail. The Z-series
    chassis identifies element 0x26 as `ZSERIES_ENCLOSURE` listed below.
    The E16 JBOD does not. The E16 identifies element 0x25 as NM_3115RL4WB66_8R5K5.

    We use this fact to ensure we are looking at the internal enclosure, and
    not a shelf. If we used a shelf to determine which node was A or B, you could
    cause the nodes to switch identities by switching the cables for the shelf.
    """
    ZSERIES_ENCLOSURE = re.compile(r'SD_9GV12P1J_12R6K4', re.M)
    ZSERIES_NODE = re.compile(r'3U20D-Encl-([AB])', re.M)

    XSERIES_ENCLOSURE = re.compile(r'\s*CELESTIC\s*(P3215-O|P3217-B)', re.M)
    XSERIES_NODEA = re.compile(r'ESCE A_(5[0-9A-F]{15})', re.M)
    XSERIES_NODEB = re.compile(r'ESCE B_(5[0-9A-F]{15})', re.M)

    MSERIES_ENCLOSURE = re.compile(r'\s*(ECStream|iX)\s*4024S([ps])', re.M)
