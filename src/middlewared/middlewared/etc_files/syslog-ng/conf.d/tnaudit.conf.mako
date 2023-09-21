<%
    import os
    import textwrap

    AUDITABLE_SERVICES = ['SMB']
    AUDIT_DIR = '/audit'

    COLUMNS = textwrap.dedent('''
        "aid varchar",
        "vers FLOAT",
        "time DATETIME",
        "addr varchar",
        "user varchar",
        "sess varchar",
        "svc varchar",
        "svc_data JSON",
        "event varchar",
        "event_data JSON",
        "success BOOLEAN"
    ''')

    VALUES = textwrap.dedent('''
        "${TNAUDIT.aid}",
        "${TNAUDIT.vers.major}.${TNAUDIT.vers.minor}",
        "${TNAUDIT.time}",
        "${TNAUDIT.addr}",
        "${TNAUDIT.user}",
        "${TNAUDIT.sess}",
        "${TNAUDIT.svc}",
        "${TNAUDIT.svc_data}",
        "${TNAUDIT.event}",
        "${TNAUDIT.event_data}",
        "${TNAUDIT.success}"
    ''')

    def to_text(tp, x):
        return ''.join((f'{tp}(', textwrap.indent(x, '  '), ')'))

    def get_filter(svc):
        txt = f'filter f_tnaudit_{svc.lower()} ' + '{ '
        txt += f'program("TNAUDIT_{svc}");' + ' };'
        return txt

    def get_db(svc):
        sql = 'sql(type(sqlite3)'
        db = f'database("{os.path.join(AUDIT_DIR, svc)}.db")'
        table = 'table("audit_${TNAUDIT.svc}_${TNAUDIT.vers.major}_${TNAUDIT.vers.minor}")'
        cols = to_text("columns", COLUMNS)
        vals = to_text("values", VALUES)
        return '\n'.join((sql, db, table, cols, vals))
%>\
parser p_tnaudit { json-parser(marker("@cee:")); };

# Convert JSON boolean into proper type for sqlite insertion
rewrite r_rewrite_success {
  subst("true", "1", value("TNAUDIT.success"));
  subst("false", "0", value("TNAUDIT.success"));
};

# Following section sets up SQL destinations for auditing targets
# Currently disk buffer is placed within the audit directory on
# ZFS. We try to batch insertions into 1K messages or 1 second
# intervals (whichever happens first). Each database target is
# managed by separate thread in syslog-ng. Indexes are disabled
# because there is no support for multi-column indexes in syslog-ng.

% for svc in AUDITABLE_SERVICES:
destination d_tnaudit_${svc.lower()} {
${textwrap.indent(get_db(svc), '  ')}
  disk-buffer(
    disk-buf-size(536870912)
    reliable(yes)
    dir(${AUDIT_DIR})
  )
  flags(explicit-commits)
  batch-lines(1000)
  batch-timeout(1000)
  indexes());
};

log {
  source(s_src);
  filter(f_tnaudit_${svc.lower()});
  parser(p_tnaudit);
  rewrite(r_rewrite_success);
  destination(d_tnaudit_${svc.lower()});
};
% endfor
