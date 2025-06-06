import enum

NVMET_KERNEL_CONFIG_DIR = '/sys/kernel/config/nvmet'
NVMET_NODE_A_ANA_GRPID = 2
NVMET_NODE_B_ANA_GRPID = 3

NVMET_DISCOVERY_NQN = 'nqn.2014-08.org.nvmexpress.discovery'
NVMET_NQN_UUID = 'nqn.2011-06.com.truenas:uuid'
NVMET_SERVICE_NAME = 'nvmet'

NVMET_MAX_NSID = 0xFFFFFFFE

NVMET_NODE_A_MAX_CONTROLLER_ID = 31999
NVMET_NODE_B_MIN_CONTROLLER_ID = 32000


class ApiMapper(enum.Enum):

    @property
    def db(self):
        return self.value[0]

    @property
    def api(self):
        return self.value[1]

    @property
    def sysfs(self):
        return self.value[2]

    @property
    def spdk(self):
        return self.value[3]

    @classmethod
    def by_db(cls, needle, raise_exception=True):
        for x in cls.__members__.values():
            if x.db == needle:
                return x

        if raise_exception:
            raise ValueError(f'Invalid db supplied: {needle}')
        else:
            return None

    @classmethod
    def by_api(cls, needle, raise_exception=True):
        for x in cls.__members__.values():
            if x.api == needle:
                return x
        if raise_exception:
            raise ValueError(f'Invalid api supplied: {needle}')
        else:
            return None


class DHCHAP_DHGROUP(ApiMapper):
    NULL = (0, None, 'null')
    B2048 = (1, '2048-BIT', 'ffdhe2048')
    B3072 = (2, '3072-BIT', 'ffdhe3072')
    B4096 = (3, '4096-BIT', 'ffdhe4096')
    B6144 = (4, '6144-BIT', 'ffdhe6144')
    B8192 = (5, '8192-BIT', 'ffdhe8192')


class DHCHAP_HASH(ApiMapper):
    SHA_256 = (1, 'SHA-256', 'hmac(sha256)')
    SHA_384 = (2, 'SHA-384', 'hmac(sha384)')
    SHA_512 = (3, 'SHA-512', 'hmac(sha512)')


class PORT_TRTYPE(ApiMapper):
    RDMA = (1, 'RDMA', 'rdma')
    FC = (2, 'FC', 'fc')
    TCP = (3, 'TCP', 'tcp')


class PORT_ADDR_FAMILY(ApiMapper):
    IPV4 = (1, 'IPV4', 'ipv4', 'IPv4')
    IPV6 = (2, 'IPV6', 'ipv6', 'IPv6')
    IB = (3, 'IB', 'ib', 'IB')
    FC = (4, 'FC', 'fc', 'FC')


def port_transport_family_generator():
    for transport in PORT_TRTYPE:
        match transport:
            case PORT_TRTYPE.RDMA | PORT_TRTYPE.TCP:
                for addr_family in (PORT_ADDR_FAMILY.IPV4, PORT_ADDR_FAMILY.IPV6):
                    yield (transport.api, addr_family.api)
            case PORT_TRTYPE.FC:
                yield (transport.api, PORT_ADDR_FAMILY.FC.api)


def similar_ports(ports: dict):
    for transport, family in port_transport_family_generator():
        yield dict(
            filter(
                lambda item: all(
                    [item[1]['addr_trtype'] == transport, item[1]['addr_adrfam'] == family]),
                ports.items()
            )
        )


class NAMESPACE_DEVICE_TYPE(ApiMapper):
    ZVOL = (1, 'ZVOL', '0')
    FILE = (2, 'FILE', '1')
