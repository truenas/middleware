import enum


class Transport(enum.Enum):
    NVME_ROCE = 'NVMe/ROCE'
    NVME_TCP = 'NVMe/TCP'

    def choices():
        return [x.value for x in Transport]


class AddressMechanism(enum.Enum):
    STATIC = 'static'
    STATIC_SET = 'static_set'
    DHCP = 'dhcp'

    def choices():
        return [x.value for x in AddressMechanism]


class ManagementProtocol(enum.Enum):
    REDFISH = 'redfish'

    def choices():
        return [x.value for x in ManagementProtocol]
