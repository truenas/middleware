import enum
import os


class GlusterConfig(enum.Enum):

    """
    Various configuration settings for gluster and friends.
    """

    # used to ensure that only one gluster
    # operation runs at any given time.
    # gluster CLI commands need to be run synchronously.
    BASE_LOCK = 'gluster_'
    CLI_LOCK = BASE_LOCK + 'cli_operation'

    # local webhook that gets sent messages on certain
    # gluster.* api calls
    LOCAL_WEBHOOK_URL = 'http://127.0.0.1:6000/_clusterevents'

    # dataset where global config is stored
    WORKDIR = '/var/db/system/glusterd'

    # when webhooks get added to the glustereventsd daemon
    # they automatically get written to a json formatted
    # file here
    WEBHOOKS_FILE = os.path.join(WORKDIR, 'events/webhooks.json')

    # to protect the api endpoint (:6000/_clusterevents)
    # TrueCommand will send us a secret that is used to
    # encode/decode JWT formatted messages. That secret
    # is stored here.
    SECRETS_FILE = os.path.join(WORKDIR, 'events/secret')

    # there are apprehensions for having an unbounded maximum
    # number of peers in a cluster wrt to ctdb/smb. Since ctdb
    # nodes are mapped to gluster peers, we cap the max number
    # of gluster peers for now
    MAX_PEERS = 20

    # Path containing dataset name where workdir was located
    # when the first gluster volume was created. This is
    # used for a sanity when generating gluster config.
    WORKDIR_DS_CACHE = '/data/.glusterd_workdir_dataset'

    UUID_BACKUP = '/data/.glusterd_uuid'

    FILES_TO_REMOVE = [
        WORKDIR_DS_CACHE,
        UUID_BACKUP
    ]


def get_gluster_workdir_dataset():
    try:
        with open(GlusterConfig.WORKDIR_DS_CACHE.value, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def set_gluster_workdir_dataset(dataset_name):
    with open(GlusterConfig.WORKDIR_DS_CACHE.value, 'w') as f:
        f.write(dataset_name)


def check_glusterd_info():
    try:
        with open(f'{GlusterConfig.WORKDIR.value}/glusterd.info', 'r') as f:
            current_uuid = f.readline()
    except FileNotFoundError:
        if not os.path.exists(GlusterConfig.UUID_BACKUP.value):
            # Glusterd is most likely starting for the first time.
            return True

        raise

    if not current_uuid.startswith('UUID'):
        raise ValueError(f'Invalid glusterd.info file: {current_uuid}')

    try:
        with open(GlusterConfig.UUID_BACKUP.value, 'r') as f:
            backup_uuid = f.readline()

    except FileNotFoundError:
        with open(GlusterConfig.UUID_BACKUP.value, 'w') as f:
            f.write(current_uuid)
            backup_uuid = current_uuid

    return current_uuid == backup_uuid
