<%
    import json
    from middlewared.plugins.cluster_linux.utils import CTDBConfig
    from pathlib import Path

    r_file = CTDBConfig.REC_FILE.value
    p_dir = CTDBConfig.PER_DB_DIR.value
    s_dir = CTDBConfig.STA_DB_DIR.value
    v_dir = CTDBConfig.VOL_DB_DIR.value

    for i in (p_dir, s_dir, v_dir):
        Path(i).mkdir(parents=True, exist_ok=True)

    try:
        ctdb_shared_vol_info = middleware.call_sync('ctdb.shared.volume.config')
    except Exception:
        middleware.logger.debug('Failed to retrieve ctdb volume information', exc_info=True)
        raise FileShouldNotExist()

    mutex_helper_config = {
        'liveness_timeout': 20,
        'check_interval': 1,
        'reclock_path': r_file,
        'volume_name': ctdb_shared_vol_info['volume_name'],
        'volfile_servers': [{'host': '127.0.0.1', 'proto': 'tcp', 'port': 0}],
        'log_file': '/var/log/ctdb/reclock_helper.log',
        'log_level': 1
    }


    # Try to extend our volfile server list
    # based on available brick configuration
    try:
        bricks = middleware.call_sync(
            'gluster.volume.query',
            [['name', '=', ctdb_shared_vol_info['volume_name']]],
            {'get': True}
        )['bricks']
    except Exception:
        bricks = []

    for brick in bricks:
        proto = 'rdma' if brick['ports']['rdma'] != 'N/A' else 'tcp'
        mutex_helper_config['volfile_servers'].append({
            'host': brick['name'].split(':')[0],
            'proto': proto,
            'port': 0
        })

    # Place in rundir to force regeneration of reclock file on fresh boot
    with open('/var/run/ctdb/gluster_reclock.conf', 'w') as f:
        f.write(json.dumps(mutex_helper_config, indent=4))

%>\
[logging]

    location = syslog:nonblocking
    log level = NOTICE

[cluster]

    recovery lock = !/usr/local/sbin/ctdb_glfs_lock

[database]

    volatile database directory = ${v_dir}
    persistent database directory = ${p_dir}
    state database directory = ${s_dir}
