import enum
import re


class RE(enum.Enum):
    M = re.compile(r"(ECStream|iX) 4024S([ps])")
    R = re.compile(r"(ECStream|iX) (FS1|FS2|DSS212S[ps])")
    R20 = re.compile(r"(iX (TrueNAS R20|2012S)p|SMC SC826-P)")
    R50 = re.compile(r"iX eDrawer4048S([12])")
    X = re.compile(r"CELESTIC (P3215-O|P3217-B)")
    ES24 = re.compile(r"(ECStream|iX) 4024J")
    ES24F = re.compile(r"(ECStream|iX) 2024J([ps])")
    MINI = re.compile(r"(TRUE|FREE)NAS-MINI")
