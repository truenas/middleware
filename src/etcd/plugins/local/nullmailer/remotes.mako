${config.get("mail.server")} smtp \
% if config.get("mail.encryption") == 'TLS':
 --starttls\
% endif
% if config.get("mail.encryption") == 'SSL':
 --ssl\
% endif
% if config.get("mail.port"):
 --port=${config.get("mail.port")}\
% endif
% if config.get("mail.auth") is True:
 --user=${config.get("mail.user")} --pass=${config.get("mail.pass")}\
% endif
