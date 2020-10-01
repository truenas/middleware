<%
    import os

    ftp = middleware.call_sync("ftp.config")
    network_configuration = middleware.call_sync("network.configuration.config")

    root_group = "wheel" if IS_FREEBSD else "root"
%>

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
MultilineRFC2228 off
DisplayLogin /var/run/proftpd/proftpd.motd
DeferWelcome off
TimeoutIdle ${ftp['timeout']}
TimeoutLogin 300
TimeoutNoTransfer 300
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
% if IS_LINUX:
LoadModule mod_ident.c
% endif
IdentLookups ${'on' if ftp['ident'] else 'off'}
UseReverseDNS ${'on' if ftp['reversedns'] else 'off'}
% if ftp['passiveportsmin']:
    PassivePorts  ${ftp['passiveportsmin']} ${ftp['passiveportsmax']}
% endif

% if IS_LINUX:
AuthOrder mod_auth_unix.c
% endif
% if ftp['onlyanonymous']:
    % if ftp['anonpath'] and os.path.isdir(ftp['anonpath']):
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
% endif
% if ftp['onlylocal']:
    <Limit LOGIN>
        AllowAll
    </Limit>
% endif
% if not (ftp['onlyanonymous'] or ftp['onlylocal']):
    <Limit LOGIN>
        AllowGroup ftp
        % if ftp['rootlogin']:
            AllowGroup ${root_group}
        % endif
        DenyAll
    </Limit>
% endif

<Global>
    RequireValidShell off
    % if ftp['defaultroot']:
        DefaultRoot ~ !${root_group}
    % endif
    % if ftp['rootlogin']:
        RootLogin on
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
    <%
        try:
            middleware.call_sync('certificate.cert_services_validation', ftp['ssltls_certificate'], 'ftp.ftp_ssltls_certificate_id')
        except Exception:
            certificate_valid = False
        else:
            certificate_valid = True
    %>
    % if certificate_valid:
        <%
            cert = middleware.call_sync('certificate.query', [['id', '=', ftp['ssltls_certificate']]], {'get': True})
        %>
        LoadModule mod_tls.c
        <IfModule mod_tls.c>
            TLSEngine on
            TLSProtocol SSLv3 TLSv1.2
            <%
                tls_options = []
                for k, v in [
                    ('allow_client_renegotiations', 'AllowClientRenegotiations'),
                    ('allow_dot_login', 'AllowDotLogin'),
                    ('allow_per_user', 'AllowPerUser'),
                    ('common_name_required', 'CommonNameRequired'),
                    ('enable_diags', 'EnableDiags'),
                    ('export_cert_data', 'ExportCertData'),
                    ('no_cert_request', 'NoCertRequest'),
                    ('no_empty_fragments', 'NoEmptyFragments'),
                    ('no_session_reuse_required', 'NoSessionReuseRequired'),
                    ('stdenvvars', 'StdEnvVars'),
                    ('dns_name_required', 'dNSNameRequired'),
                    ('ip_address_required', 'iPAddressRequired'),
                ]:
                    if ftp[f'tls_opt_{k}']:
                        tls_options.append(v)
            %>
            % if tls_options:
                TLSOptions ${' '.join(tls_options)}
            % endif
            TLSRSACertificateFile "${cert['certificate_path']}"
            TLSRSACertificateKeyFile "${cert['privatekey_path']}"
            % if cert['chain']:
                TLSCertificateChainFile "${cert['certificate_path']}"
            % endif
            TLSVerifyClient off
            TLSRequired ${ftp['tls_policy']}
        </IfModule>
    % endif
% endif

<IfModule mod_ban.c>
    BanEngine off
    BanControlsACLs all allow group ${root_group}
    BanLog /var/log/proftpd/ban.log
    BanMessage Host %a has been banned
    # -m "mod_ban/rule"
    # -v "concat('  BanOnEvent ',event,' ',occurrence,'/',timeinterval,' ',expire)" -n
    # -b
    BanTable /var/run/proftpd/ban.tab
</IfModule>

${ftp['options']}

<IfModule mod_delay.c>
    DelayEngine on
    DelayTable /var/run/proftpd/proftpd.delay
</IfModule>

<IfModule mod_wrap.c>
    TCPAccessFiles "/etc/hosts.allow" "/etc/hosts.deny"
    TCPAccessSyslogLevels info warn
    TCPServiceName ftpd
</ifModule>
