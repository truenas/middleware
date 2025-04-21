import enum


class RDMAprotocols(enum.Enum):
    NFS = 'NFS'
    ISER = 'ISER'
    NVMET = 'NVMET'

    def values():
        return [a.value for a in RDMAprotocols]
