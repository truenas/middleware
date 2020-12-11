# This is a global variable used to ensure that only
# one gluster operation runs at any given time.
# Gluster CLI commands need to be run synchronously.
GLUSTER_JOB_LOCK = 'gluster_operation'
