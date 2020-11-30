<%
    from pathlib import Path
    from middlewared.plugins.cluster_linux.utils import CTDBLocal, CTDBCluster
    from middlewared.plugins.smb import SMBHAMODE

    clustered = SMBHAMODE[middleware.call_sync('smb.get_smb_ha_mode')] == SMBHAMODE.CLUSTERED
    if not clustered:
        return

    r_file = CTDBCluster.RECOVERY_FILE.value
    v_dir = CTDBLocal.SMB_VOLATILE_DB_DIR.value
    p_dir = CTDBLocal.SMB_PERSISTENT_DB_DIR.value
    s_dir = CTDBLocal.SMB_STATE_DB_DIR.value

    try:
        for i in (v_dir, p_dir, s_dir):
            p = Path(i)
            p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        middleware.logger.error('Failed creating %s with error %r', i, e)
        return

%>\
[logging]

    location = syslog:nonblocking
    log level = NOTICE

[cluster]

    recovery lock = ${r_file}

[database]

    volatile database directory = ${v_dir}
    persistent database directory = ${p_dir}
    state database directory = ${s_dir}
