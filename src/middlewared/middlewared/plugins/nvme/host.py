import filecmp
import shutil
import uuid
import pathlib

NQN_UUID_PREFIX = 'nqn.2011-06.com.truenas:uuid:'
DATA_NVME_PATH = '/data/subsystems/nvme'
LIVE_NVMENQN_PATH = '/etc/nvme/hostnqn'
LIVE_NVMEID_PATH = '/etc/nvme/hostid'


def setup(middleware):
    data_nvme = pathlib.Path(DATA_NVME_PATH)
    if not data_nvme.exists():
        data_nvme.mkdir()

    # /etc/nvme/hostnqn
    data_hostnqn = data_nvme / 'hostnqn'
    if not data_hostnqn.exists():
        data_hostnqn.write_text(f'{NQN_UUID_PREFIX}{uuid.uuid4()}\n')
        middleware.logger.debug("Generated hostnqn")
    if not filecmp.cmp(data_hostnqn, LIVE_NVMENQN_PATH):
        shutil.copy2(data_hostnqn, LIVE_NVMENQN_PATH)
        middleware.logger.debug(f"Wrote {LIVE_NVMENQN_PATH}")

    # /etc/nvme/hostid
    data_hostid = data_nvme / 'hostid'
    if not data_hostid.exists():
        data_hostid.write_text(f'{uuid.uuid4()}\n')
        middleware.logger.debug("Generated hostid")
    if not filecmp.cmp(data_hostid, LIVE_NVMEID_PATH):
        shutil.copy2(data_hostid, LIVE_NVMEID_PATH)
        middleware.logger.debug(f"Wrote {LIVE_NVMEID_PATH}")
