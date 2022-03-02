<%
    from middlewared.utils import filter_list

    users = filter_list(render_ctx['user.query'], [["sudo", "=", True]])
    groups = filter_list(render_ctx['group.query'], [["sudo", "=", True]])

    def sudo_commands(commands):
        commands = list(filter(None, [command.strip() for command in commands]))
        if not commands:
            return "ALL"
        return ", ".join(map(sudo_command, commands))

    def sudo_command(command):
        for c in ["\\", ",", ":", "="]:
            command = command.replace(c, "\\" + c)
        return command

%>\
root ALL=(ALL:ALL) ALL
% for user in users:
% if user['sudo_nopasswd']:
${user['username']} ALL=(ALL) NOPASSWD: ${sudo_commands(user['sudo_commands'])}
% else:
${user['username']} ALL=(ALL) ${sudo_commands(user['sudo_commands'])}
% endif
% endfor
% for group in groups:
% if group['sudo_nopasswd']:
${f'%{group["group"]}'} ALL=(ALL) NOPASSWD: ${sudo_commands(group['sudo_commands'])}
% else:
${f'%{group["group"]}'} ALL=(ALL) ${sudo_commands(group['sudo_commands'])}
% endif
% endfor
Defaults syslog_goodpri = debug
Defaults secure_path = /sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin

# Let find_alias_for_smtplib.py runs as root (it needs database access)
ALL ALL=(ALL) NOPASSWD: /etc/find_alias_for_smtplib.py
ALL ALL=(ALL) NOPASSWD: /etc/find_alias_for_smtplib.sh
nut ALL=(root) NOPASSWD: /usr/local/bin/custom-upssched-cmd
