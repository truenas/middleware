from enum import StrEnum


class Vendors(StrEnum):
    """The set of possible vendor names in /data/.vendor"""
    TRUENAS_SCALE = "TrueNAS Scale"
    HEXOS = "HexOS"
