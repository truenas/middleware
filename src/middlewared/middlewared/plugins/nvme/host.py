import filecmp
import shutil
import uuid
import pathlib

NQN_UUID_PREFIX = 'nqn.2011-06.com.truenas:uuid:'
DATA_NVME_PATH = '/data/subsystems/nvme'
LIVE_NVMENQN_PATH = '/etc/nvme/hostnqn'
LIVE_NVMEID_PATH = '/etc/nvme/hostid'


def setup(middleware):
    try:
        data_nvme = pathlib.Path(DATA_NVME_PATH)
        try:
            data_nvme.mkdir()
        except FileExistsError:
            pass

        # /etc/nvme/hostnqn
        data_hostnqn = data_nvme / 'hostnqn'
        if not data_hostnqn.exists():
            data = f'{NQN_UUID_PREFIX}{uuid.uuid4()}'
            data_hostnqn.write_text(f'{data}\n')
            middleware.logger.debug("Generated hostnqn: %s", data)
        if not filecmp.cmp(data_hostnqn, LIVE_NVMENQN_PATH):
            shutil.copy2(data_hostnqn, LIVE_NVMENQN_PATH)
            middleware.logger.debug("Wrote %s", LIVE_NVMENQN_PATH)

        # /etc/nvme/hostid
        data_hostid = data_nvme / 'hostid'
        if not data_hostid.exists():
            data = f'{uuid.uuid4()}'
            data_hostid.write_text(f'{data}\n')
            middleware.logger.debug("Generated hostid: %s", data)
        if not filecmp.cmp(data_hostid, LIVE_NVMEID_PATH):
            shutil.copy2(data_hostid, LIVE_NVMEID_PATH)
            middleware.logger.debug("Wrote %s", LIVE_NVMEID_PATH)
    except Exception:
        middleware.logger.debug("Failed to generate nvme host info", exc_info=True)
