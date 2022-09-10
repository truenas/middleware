from os import environ


CLUSTER_INFO = {
    'PUBLIC_IP01': environ.get('PUBLIC_IP01'),
    'PUBLIC_IP01_DNS': environ.get('PUBLIC_IP01_DNS'),
    'PUBLIC_IP02': environ.get('PUBLIC_IP02'),
    'PUBLIC_IP02_DNS': environ.get('PUBLIC_IP02_DNS'),
    'PUBLIC_IP03': environ.get('PUBLIC_IP03'),
    'PUBLIC_IP03_DNS': environ.get('PUBLIC_IP03_DNS'),
    'NODE_A_IP': environ.get('NODE_A_IP'),
    'NODE_A_DNS': environ.get('NODEA'),
    'NODE_B_IP': environ.get('NODE_B_IP'),
    'NODE_B_DNS': environ.get('NODEB'),
    'NODE_C_IP': environ.get('NODE_C_IP'),
    'NODE_C_DNS': environ.get('NODEC'),
    'NETMASK': int(environ.get('NETMASK')),
    'INTERFACE': environ.get('INTERFACE'),
    'DEFGW': environ.get('DEFGW'),
    'DNS1': environ.get('DNS1'),
    'APIUSER': environ.get('APIUSER'),
    'APIPASS': environ.get('APIPASS'),
    'ZPOOL_DISK': environ.get('ZPOOL_DISK'),
    'ZPOOL': environ.get('ZPOOL'),
    'GLUSTER_VOLUME': environ.get('GLUSTER_VOLUME'),
}

CLUSTER_ADS = {
    'DOMAIN': environ.get('AD_DOMAIN'),
    'USERNAME': environ.get('AD_USERNAME'),
    'PASSWORD': environ.get('AD_PASSWORD'),
    'NETBIOS': environ.get('NETBIOS'),
}

CLUSTER_LDAP = {
    'HOSTNAME': environ.get('LDAP_HOSTNAME'),
    'BASEDN': environ.get('LDAP_BASEDN'),
    'BINDDN': environ.get('LDAP_BINDDN'),
    'BINDPW': environ.get('LDAP_BINDPW'),
    'TEST_USERNAME': environ.get('LDAP_TEST_USERNAME'),
    'TEST_PASSWORD': environ.get('LDAP_TEST_PASSWORD'),
    'TEST_GROUPNAME': environ.get('LDAP_TEST_GROUPNAME'),
}

TIMEOUTS = {
    'FUSE_OP_TIMEOUT': environ.get('FUSE_OP_TIMEOUT', 10),
    'FAILOVER_WAIT_TIMEOUT': environ.get('FAILOVER_WAIT_TIMEOUT', 10),
    'MONITOR_TIMEOUT': environ.get('MONITOR_TIMEOUT', 20),
    'CTDB_IP_TIMEOUT': environ.get('CTDB_IP_TIMEOUT', 20),
    'VOLUME_TIMEOUT': environ.get('VOLUME_TIMEOUT', 120),
}

CLEANUP_TEST_DIR = 'tests/cleanup'
INTERNAL_DS = '.glusterfs'
BRICK_NAME = 'brick0'
DATASET_HIERARCHY = f'{CLUSTER_INFO["ZPOOL"]}/{INTERNAL_DS}/{CLUSTER_INFO["GLUSTER_VOLUME"]}/{BRICK_NAME}'
BRICK_PATH = f'/mnt/{DATASET_HIERARCHY}'
CLUSTER_IPS = [CLUSTER_INFO['NODE_A_IP'], CLUSTER_INFO['NODE_B_IP'], CLUSTER_INFO['NODE_C_IP']]
PUBLIC_IPS = [CLUSTER_INFO['PUBLIC_IP01'], CLUSTER_INFO['PUBLIC_IP02'], CLUSTER_INFO['PUBLIC_IP03']]
GLUSTER_PEERS_DNS = [CLUSTER_INFO['NODE_A_DNS'], CLUSTER_INFO['NODE_B_DNS'], CLUSTER_INFO['NODE_C_DNS']]
