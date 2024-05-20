<%
    users = render_ctx['user.query']
    groups = render_ctx['group.query']

    def sudo_entry(commands, commands_nopasswd):
        entry = []
        if commands:
            entry.append(sudo_commands(commands))
        if commands_nopasswd:
            entry.append("NOPASSWD: " + sudo_commands(commands_nopasswd))
        return ", ".join(entry)

    def sudo_commands(commands):
        commands = list(filter(None, [command.strip() for command in commands]))
        return ", ".join(map(sudo_command, commands))

    def sudo_command(command):
        for c in ["\\", ",", ":", "="]:
            command = command.replace(c, "\\" + c)
        return command

%>\
root ALL=(ALL:ALL) ALL
% for user in users:
% if user['sudo_commands'] or user['sudo_commands_nopasswd']:
${user['username']} ALL=(ALL) ${sudo_entry(user['sudo_commands'], user['sudo_commands_nopasswd'])}
% endif
% endfor
% for group in groups:
% if group['sudo_commands'] or group['sudo_commands_nopasswd']:
${f'%{group["group"]}'} ALL=(ALL) ${sudo_entry(group['sudo_commands'], group['sudo_commands_nopasswd'])}
% endif
% endfor
Defaults syslog_goodpri = debug
Defaults secure_path = /sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
Defaults log_subcmds
Defaults log_format=json

# Let find_alias_for_smtplib.py runs as root (it needs database access)
ALL ALL=(ALL) NOPASSWD: /etc/find_alias_for_smtplib.py
ALL ALL=(ALL) NOPASSWD: /etc/find_alias_for_smtplib.sh
nut ALL=(root) NOPASSWD: /usr/local/bin/custom-upssched-cmd
