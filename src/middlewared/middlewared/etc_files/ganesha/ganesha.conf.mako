<%
    import itertools

    config = middleware.call_sync("nfs.config")

    shares = middleware.call_sync("sharing.nfs.query", [["enabled", "=", True]])
    if not shares:
        raise FileShouldNotExist()

    kerberos_keytabs = middleware.call_sync("kerberos.keytab.query")

    gc = middleware.call_sync("network.configuration.config")

    # call this here so that we don't have to call this
    # n times (n being the number of shares in db)
    peers = []
    if middleware.call_sync("service.started", "glusterd"):
        peers = middleware.call_sync("gluster.peer.status")

    bindip = middleware.call_sync("nfs.bindip", config)
    sec = middleware.call_sync("nfs.sec", config, kerberos_keytabs)

    export_id = itertools.count(1)
%>

NFS_CORE_PARAM {
    % if config["mountd_port"]:
    MNT_Port = ${config["mountd_port"]};
    % endif;
    % if config["rpclockd_port"]:
    NLM_Port = ${config["rpclockd_port"]};
    % endif;
    % if bindip:
    Bind_addr = ${bindip[0]};
    % endif;
}
% if config["v4"]:
NFSV4 {
    % if config["v4_v3owner"]:
    Allow_Numeric_Owners = true;
    Only_Numeric_Owners = true;
    % endif;
    % if config["v4_domain"]:
    DomainName = ${config["v4_domain"]};
    % endif;
}
% endif;
% if config["v4_krb_enabled"]:
NFS_KRB5 {
    % if gc.get("hostname_virtual"):
    PrincipalName = nfs@${f'{gc["hostname_virtual"]}.{gc["domain"]}'};
    % else:
    PrincipalName = nfs@${gc["domain"]};
    % endif;
    KeytabPath = /etc/krb5.keytab;
    Active_krb5 = YES;
}
% endif;
% if sec:
EXPORT_DEFAULTS {
    SecType = ${", ".join(sec)};
}
% endif;
% for share in shares:
    <%
        locked_datasets = None
        if share['locked']:
            if not locked_datasets:
                locked_datasets = middleware.call_sync('zfs.dataset.locked_datasets')
            middleware.call_sync('sharing.nfs.generate_locked_alert', share['id'])

        clients = share["networks"] + share["hosts"]
    %>

    <%
        share["uses_gluster"] = False
        share["gluster_node"] = None
    %>
    % for path, alias in zip(share["paths"], share["aliases"] or share["paths"]):
    <%
        gvol = path.split("/")
        if len(gvol) > 3 and gvol[3] == ".glusterfs":
            share["uses_gluster"] = True
            if peers:
                share["gluster_node"] = peers[0]["hostname"]
            else:
                middleware.logger.debug(
                    'Skipping generation of %r path.'
                    'It is part of a gluster path, but gluster peers were not detected', path
                )

        if share['locked'] and middleware.call_sync('pool.dataset.path_in_locked_datasets', path, locked_datasets):
            middleware.logger.debug(
                'Skipping generation of %r path for NFS share as the underlying resource is locked', path
            )
            continue
    %>
EXPORT {
    Export_Id = ${next(export_id)};
    Path = ${path};
    % if not config["v4"]:
    Protocols = 3;
    % else:
    Protocols = 3, 4;
    % endif;
    % if config["v4"] and share["aliases"]:
    Pseudo = ${alias};
    % elif not config["v4"] and share["aliases"]:
    Tag = ${alias.lstrip('/')};
    % elif config["v4"] and not share["aliases"]:
    Pseudo = /${path.split('/')[-1]};
    % endif;
    % if config["udp"]:
    Transports = TCP, UDP;
    % else:
    Transports = TCP;
    % endif;
    % if clients:
    Access_Type = None;
    CLIENT {
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
    % endif;
    % if group:
    Anonymous_Gid = ${group[0]["gid"]};
    % endif;
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
    % endif;
    % if group:
    Anonymous_Gid = ${group[0]["gid"]};
    % endif;
    % else:
    Squash = None;
    % endif;
    % if config["userd_manage_gids"]:
    Manage_Gids = true;
    % endif;
    % if config["v4"] and share["security"]:
    SecType = ${", ".join([s.lower() for s in share["security"]])};
    % endif;
    % if share["uses_gluster"] and share["gluster_node"] is not None:
    FSAL {
        Name = "GLUSTER";
        Hostname = "${share["gluster_node"]}";
        Volume = "${path.split("/")[4]}";
    }
    % else:
    FSAL {
        Name = VFS;
    }
    % endif;
}
    % endfor;
% endfor;
