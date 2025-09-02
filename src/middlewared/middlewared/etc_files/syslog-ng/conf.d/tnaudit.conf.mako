<%
    import textwrap

    from middlewared.plugins.audit.utils import AUDITED_SERVICES, audit_file_path, AUDIT_DATASET_PATH, audit_custom_section

    COLUMNS = textwrap.dedent('''
        "audit_id varchar",
        "message_timestamp INT",
        "timestamp DATETIME",
        "address varchar",
        "username varchar",
        "session varchar",
        "service varchar",
        "service_data JSON",
        "event varchar",
        "event_data JSON",
        "success BOOLEAN"
    ''')

    VALUES = textwrap.dedent('''
        "${TNAUDIT.aid}",
        "${C_UNIXTIME}",
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
        db = f'database("{audit_file_path(svc)}")'
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

% for svc, vers in AUDITED_SERVICES:
destination d_tnaudit_${svc.lower()} {
${textwrap.indent(get_db(svc), '  ')}
  disk-buffer(
    disk-buf-size(536870912)
    reliable(yes)
    dir(${AUDIT_DATASET_PATH})
  )
  flags(explicit-commits)
  batch-lines(1000)
  batch-timeout(1000)
  indexes());
};

% if not audit_custom_section(svc, 'log'):
log {
% if svc == 'MIDDLEWARE':
  source(s_tn_middleware);
% elif svc == 'SYSTEM':
  source(s_tn_auditd);
% else:
  source(s_src);
% endif
  filter(f_tnaudit_${svc.lower()});
  parser(p_tnaudit);
  rewrite(r_rewrite_success);
  destination(d_tnaudit_${svc.lower()});
  flags(final);
};
%endif
% endfor

# SUDO service is a special case because we do not control the format of the
# events it logs.  Instead we will MAP the events into our database, plus we
# retain the original sudo generated JSON in the event_data
<%text>
filter f_tnaudit_sudo_accept { match(".+" value("sudo.accept.uuid")) };
filter f_tnaudit_sudo_reject { match(".+" value("sudo.reject.uuid")) };

parser p_tnaudit_sudo_accept {
  date-parser(
      format("%Y%m%d%H%M%SZ")
      template("${sudo.accept.server_time.iso8601}")
  );
};
parser p_tnaudit_sudo_reject {
  date-parser(
      format("%Y%m%d%H%M%SZ")
      template("${sudo.reject.server_time.iso8601}")
  );
};

rewrite r_rewrite_sudo_common {
  set("${PID}", value("TNAUDIT.sess"));
  set("SUDO", value("TNAUDIT.svc"));
  set("0", value("TNAUDIT.vers.major"));
  set("1", value("TNAUDIT.vers.minor"));
  set('{"vers": {"major": 0, "minor": 1}}', value("TNAUDIT.svc_data"));
  set("$(format-json --scope none sudo.*)", value("TNAUDIT.event_data"));
};
rewrite r_rewrite_sudo_accept {
  set("${sudo.accept.uuid}", value("TNAUDIT.aid"));
  fix-time-zone("UTC");
  set('${S_YEAR}-${S_MONTH}-${S_DAY} ${S_HOUR}:${S_MIN}:${S_SEC}.$(substr "${sudo.accept.server_time.nanoseconds}" "0" "6")', value("TNAUDIT.time"));
  set("${sudo.accept.submithost}", value("TNAUDIT.addr"));
  set("${sudo.accept.submituser}", value("TNAUDIT.user"));
  set("ACCEPT", value("TNAUDIT.event"));
  set("1", value("TNAUDIT.success"));
};
rewrite r_rewrite_sudo_reject {
  set("${sudo.reject.uuid}", value("TNAUDIT.aid"));
  fix-time-zone("UTC");
  set('${S_YEAR}-${S_MONTH}-${S_DAY} ${S_HOUR}:${S_MIN}:${S_SEC}.$(substr "${sudo.reject.server_time.nanoseconds}" "0" "6")', value("TNAUDIT.time"));
  set("${sudo.reject.submithost}", value("TNAUDIT.addr"));
  set("${sudo.reject.submituser}", value("TNAUDIT.user"));
  set("REJECT", value("TNAUDIT.event"));
  set("0", value("TNAUDIT.success"));
};

log {
  source(s_src);
  filter(f_tnaudit_sudo);
  parser(p_tnaudit);
  filter(f_tnaudit_sudo_accept);
  parser(p_tnaudit_sudo_accept);
  rewrite(r_rewrite_sudo_accept);
  rewrite(r_rewrite_sudo_common);
  destination(d_tnaudit_sudo);
  flags(final);
};
log {
  source(s_src);
  filter(f_tnaudit_sudo);
  parser(p_tnaudit);
  filter(f_tnaudit_sudo_reject);
  parser(p_tnaudit_sudo_reject);
  rewrite(r_rewrite_sudo_reject);
  rewrite(r_rewrite_sudo_common);
  destination(d_tnaudit_sudo);
  flags(final);
};
</%text>
