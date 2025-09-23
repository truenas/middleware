<%
    import os

    ftp = render_ctx['ftp.config']
    network_configuration = render_ctx['network.configuration.config']
    directory_services = render_ctx['directoryservices.config']

    # Confirm necessary directories, files and permissions
    os.makedirs("/var/log/proftpd", exist_ok=True)
    os.makedirs("/var/run/proftpd", exist_ok=True)
    with open("/var/log/wtmp", "a+")as fd:
        os.fchmod(fd.fileno(), 0o644)

    if ftp['anonpath']:
        anonpath = os.path.isdir(ftp['anonpath'])
    else:
        anonpath = False
%>
#
# ProFTPD configuration file
#

# Includes DSO modules
Include /etc/proftpd/modules.conf

ServerName "${network_configuration['hostname_local']} FTP Server"
ServerType standalone
DefaultServer on
DefaultAddress localhost
UseIPv6 on
Port ${ftp['port']}
User nobody
Group nogroup
Umask ${ftp['filemask']} ${ftp['dirmask']}
SyslogFacility ftp
DisplayLogin /etc/proftpd/proftpd.motd
DeferWelcome off
TimeoutIdle ${ftp['timeout']}
TimeoutLogin 300
TimeoutNoTransfer ${ftp['timeout_notransfer']}
TimeoutStalled 3600
MaxInstances none
% if ftp['clients']:
    MaxClients ${ftp['clients']}
% endif
% if ftp['ipconnections']:
    MaxConnectionsPerHost ${ftp['ipconnections']}
% endif
% if ftp['loginattempt']:
    MaxLoginAttempts ${ftp['loginattempt']}
% endif
DefaultTransferMode ascii
AllowForeignAddress ${'on' if ftp['fxp'] else 'off'}
% if ftp['masqaddress']:
    MasqueradeAddress ${ftp['masqaddress']}
% endif
LoadModule mod_ident.c
IdentLookups ${'on' if ftp['ident'] else 'off'}
UseReverseDNS ${'on' if ftp['reversedns'] else 'off'}
% if ftp['passiveportsmin']:
    PassivePorts  ${ftp['passiveportsmin']} ${ftp['passiveportsmax']}
% endif

% if directory_services['enable']:
AuthPAMConfig proftpd
AuthOrder mod_auth_pam.c* mod_auth_unix.c
% else:
AuthOrder mod_auth_unix.c
% endif

% if ftp['onlyanonymous'] and anonpath:
<Anonymous ${ftp['anonpath']}>
    User ftp
    Group ftp
    UserAlias anonymous ftp
    % if ftp['anonuserbw']:
        TransferRate STOR ${ftp['anonuserbw']}
    % endif
    % if ftp['anonuserdlbw']:
        TransferRate RETR ${ftp['anonuserdlbw']}
    % endif
    <Limit LOGIN>
        AllowAll
    </Limit>
</Anonymous>
% endif
% if ftp['onlylocal']:
<Limit LOGIN>
    AllowAll
</Limit>
% endif
% if not (ftp['onlyanonymous'] or ftp['onlylocal']):
<Limit LOGIN>
    AllowGroup ftp
    DenyAll
</Limit>
% endif

<Global>
    RequireValidShell off
    % if ftp['defaultroot']:
        DefaultRoot ~ !root
    % endif
    AllowOverwrite on
    % if ftp['resume']:
        AllowRetrieveRestart on
        AllowStoreRestart on
    % endif
    DeleteAbortedStores off
    % if ftp['localuserbw']:
        TransferRate STOR ${ftp['localuserbw']}
    % endif
    % if ftp['localuserdlbw']:
        TransferRate RETR ${ftp['localuserdlbw']}
    % endif
    TimesGMT off
</Global>

% if ftp['tls']:
Include /etc/proftpd/tls.conf
% endif

${ftp['options']}
