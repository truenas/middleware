<%
    import itertools

    config = middleware.call_sync("nfs.config")

    shares = middleware.call_sync("sharing.nfs.query", [["enabled", "=", True]])

    kerberos_keytabs = middleware.call_sync("kerberos.keytab.query")

    gc = middleware.call_sync("network.configuration.config")

    bindip = middleware.call_sync("nfs.bindip", config)
    sec = middleware.call_sync("nfs.sec", config, kerberos_keytabs)

    export_id = itertools.count(1)
%>

NFS_CORE_PARAM
{
    % if config["mountd_port"]:
        MNT_Port = ${config["mountd_port"]};
    % endif;
    % if config["rpclockd_port"]:
        NLM_Port = ${config["rpclockd_port"]};
    % endif;

    % if bindip:
        Bind_addr = ${bindip[0]};
    % endif;

    % if config["v4"]:
        Protocols = 3, 4;
    % else:
        Protocols = 3;
    % endif;
}

% if config["v4"]:
    NFSV4
    {
        % if config["v4_v3owner"]:
            Allow_Numeric_Owners = true;
            Only_Numeric_Owners = true;
        % endif;
        % if config["v4_domain"]:
            DomainName = ${config["v4_domain"]};
        % endif;
    }

    % if config["v4_krb_enabled"]:
        NFS_KRB5
        {
            % if gc.get("hostname_virtual"):
                PrincipalName = nfs@${f'{gc["hostname_virtual"]}.{gc["domain"]}'};
            % else:
                PrincipalName = nfs@${gc["domain"]};
            % endif;
            KeytabPath = /etc/krb5.keytab;
            Active_krb5 = YES;
        }
    % endif;
% endif;

EXPORT_DEFAULTS
{
    % if sec:
        SecType = ${", ".join(sec)};
    % endif
}

% for share in shares:
    <%
        locked_datasets = None
        if share['locked']:
            if not locked_datasets:
                locked_datasets = middleware.call_sync('zfs.dataset.locked_datasets')
            middleware.call_sync('sharing.nfs.generate_locked_alert', share['id'])

        clients = share["networks"] + share["hosts"]
    %>

    % for path, alias in zip(share["paths"], share["aliases"] or share["paths"]):
    <%
        if share['locked'] and middleware.call_sync('pool.dataset.path_in_locked_datasets', path, locked_datasets):
            middleware.logger.debug(
                'Skipping generation of %r path for NFS share as the underlying resource is locked', path
            )
            continue
    %>\
        EXPORT
        {
            Export_Id = ${next(export_id)};
            Path = ${path};
            % if config["v4"]:
                Pseudo = ${alias};
            % endif;
            Tag = ${alias};

            % if config["udp"]:
                Transports = TCP, UDP;
            % else:
                Transports = TCP;
            % endif

            % if clients:
                Access_Type = None;

                CLIENT
                {
                    Clients = ${", ".join(clients)};

                    Access_Type = ${"RO" if share["ro"] else "RW"};
                }
            % else:
                Access_Type = ${"RO" if share["ro"] else "RW"};
            % endif;

            % if share["mapall_user"]:
                Squash = AllSquash;
                <%
                user = middleware.call_sync(
                    "user.query",
                    [("username", "=", share["mapall_user"])],
                    {"extra": {"search_dscache": True}},
                )
                group = []
                if share["mapall_group"]:
                    group = middleware.call_sync(
                        "group.query",
                        [("group", "=", share["mapall_group"])],
                        {"extra": {"search_dscache": True}},
                    )
                %>
                % if user:
                    Anonymous_Uid = ${user[0]["uid"]};
                % endif
                % if group:
                    Anonymous_Gid = ${group[0]["gid"]};
                % endif
            % elif share["maproot_user"]:
                Squash = RootSquash;
                <%
                user = middleware.call_sync(
                    "user.query",
                    [("username", "=", share["maproot_user"])],
                    {"extra": {"search_dscache": True}},
                )
                group = []
                if share["maproot_group"]:
                    group = middleware.call_sync(
                        "group.query",
                        [("group", "=", share["maproot_group"])],
                        {"extra": {"search_dscache": True}},
                    )
                %>
                % if user:
                    Anonymous_Uid = ${user[0]["uid"]};
                % endif
                % if group:
                    Anonymous_Gid = ${group[0]["gid"]};
                % endif
            % else:
                Squash = None;
            % endif

            % if config["userd_manage_gids"]:
                Manage_Gids = true;
            % endif;

            % if config["v4"] and share["security"]:
                SecType = ${", ".join([s.lower() for s in share["security"]])};
            % endif

            FSAL
            {
                Name = VFS;
            }
        }
    % endfor
% endfor
