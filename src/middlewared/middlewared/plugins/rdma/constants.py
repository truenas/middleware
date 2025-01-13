import enum


class RDMAprotocols(enum.Enum):
    NFS = 'NFS'
    ISER = 'ISER'

    def values():
        return [a.value for a in RDMAprotocols]
