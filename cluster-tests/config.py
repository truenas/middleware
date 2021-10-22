from os import environ


CLUSTER_INFO = {
    'PUBLIC_IPS': environ.get('PUBLIC_IPS', '').split(),
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
    'PASSWORD': enviorn.get('AD_PASSWORD')
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

INTERNAL_DS = '.glusterfs'
BRICK_NAME = 'brick0'
DATASET_HIERARCHY = f'{CLUSTER_INFO["ZPOOL"]}/{INTERNAL_DS}/{CLUSTER_INFO["GLUSTER_VOLUME"]}/{BRICK_NAME}'
BRICK_PATH = f'/mnt/{DATASET_HIERARCHY}'
CLUSTER_IPS = [CLUSTER_INFO['NODE_A_IP'], CLUSTER_INFO['NODE_B_IP'], CLUSTER_INFO['NODE_C_IP']]
