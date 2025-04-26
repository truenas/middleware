import uuid

from .constants import NVMET_NQN_UUID


def uuid_nqn():
    # If we wanted a "nqn.2014-08.org.nvmexpress: we could first
    # try to read from /etc/nvme/hostnqn
    # However, since this will be shared between nodes HA nodes,
    # there is an argument that it should not be the hostnqn of
    # either node.
    return f'{NVMET_NQN_UUID}:{uuid.uuid4()}'
