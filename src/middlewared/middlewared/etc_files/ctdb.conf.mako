<%
    from middlewared.plugins.cluster_linux.utils import CTDBConfig
    from pathlib import Path

    r_file = CTDBConfig.GM_RECOVERY_FILE.value
    p_dir = CTDBConfig.PER_DB_DIR.value
    s_dir = CTDBConfig.STA_DB_DIR.value
    v_dir = CTDBConfig.VOL_DB_DIR.value

    for i in (p_dir, s_dir, v_dir):
        Path(i).mkdir(parents=True, exist_ok=True)
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
