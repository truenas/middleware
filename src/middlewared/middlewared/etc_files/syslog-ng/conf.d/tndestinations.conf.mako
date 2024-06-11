########################
# Destinations
########################
# First some standard logfile
#
destination d_auth { file("/var/log/auth.log"); };
destination d_cron { file("/var/log/cron.log"); };
destination d_daemon { file("/var/log/daemon.log"); };
destination d_kern { file("/var/log/kern.log"); };
destination d_mail { file("/var/log/mail.log"); };
destination d_syslog { file("/var/log/syslog"); };
destination d_user { file("/var/log/user.log"); };
destination d_uucp { file("/var/log/uucp.log"); };

# Some 'catch-all' logfiles.
#
destination d_debug { file("/var/log/debug"); };
destination d_error { file("/var/log/error"); };
destination d_messages { file("/var/log/messages"); };

# The root's console.
#
destination d_console { usertty("root"); };

# Virtual console.
#
destination d_console_all { getvirtconsole(); };

destination d_xconsole { pipe("/dev/xconsole"); };

# Drop logs
destination d_null { file("/dev/null"); };
