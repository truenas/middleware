<%
	users = middleware.call_sync('user.query', [["sudo", "=", True]])
	groups = middleware.call_sync('group.query', [["sudo", "=", True]])
	ups_user = "nut" if IS_LINUX else "uucp"

%>\
% if IS_LINUX:
root ALL=(ALL:ALL) ALL
% endif
% for user in users:
${user['username']} ALL=(ALL) ALL
% endfor
% for group in groups:
${f'%{group["group"]}'} ALL=(ALL) ALL
% endfor
Defaults syslog_goodpri = debug
Defaults secure_path = /sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin

# Let find_alias_for_smtplib.py runs as root (it needs database access)
ALL ALL=(ALL) NOPASSWD: /etc/find_alias_for_smtplib.py
ALL ALL=(ALL) NOPASSWD: /etc/find_alias_for_smtplib.sh
${ups_user} ALL=(root) NOPASSWD: /usr/local/bin/custom-upssched-cmd
