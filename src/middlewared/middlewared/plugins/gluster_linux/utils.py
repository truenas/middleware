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
