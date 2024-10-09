import enum


class RDMAprotocols(enum.Enum):
    NFS = 'NFS'
    ISER = 'iSER'

    def values():
        return [a.value for a in RDMAprotocols]
