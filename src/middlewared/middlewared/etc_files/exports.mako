<%
    import os

    def do_map(share, map_type):
        output = []
        if share[f'{map_type}_user']:
            uid = middleware.call_sync(
                'user.get_user_obj',
                {'username': share[f'{map_type}_user']}
            )['pw_uid']
            output.append(f'anonuid={uid}')

        if share[f'{map_type}_group']:
            gid = middleware.call_sync(
                'group.get_group_obj',
                {'groupname': share[f'{map_type}_group']}
            )['gr_gid']
            output.append(f'anongid={gid}')

        return output

    def generate_options(share):
        params = []
        all_squash = False
        if share["security"]:
            sec = f'sec={":".join(share["security"])}'
            params.append(sec.lower())

        if not share["ro"]:
            params.append("rw")

        try:
            mapall = do_map(share, "mapall")
        except KeyError:
            self.logger.warning(
                "NSS lookup for anonymous account failed. "
                "disabling NFS exports.",
                exc_info = True
            )
            raise FileShouldNotExist()

        if mapall:
            params.extend(mapall)
            params.append("all_squash")

        try:
            maproot = do_map(share, "maproot")
        except KeyError:
            self.logger.warning(
                "NSS lookup for anonymous account failed. "
                "disabling NFS exports.",
                exc_info = True
            )
            raise FileShouldNotExist()

        if maproot:
            params.extend(maproot)

        params.append("subtree_check")
        return ','.join(params)

    entries = []
    config = middleware.call_sync("nfs.config")
    shares = middleware.call_sync("sharing.nfs.query", [
        ["enabled", "=", True],
        ["locked", "=", False],
    ])

    for share in shares:
        opts = generate_options(share)
        for path in share["paths"]:
            if not os.path.exists(path):
                continue

            anonymous = True
            options = []

            for host in share["hosts"]:
                options.append(f'{host}({opts})')
                anonymous = False

            for network in share["networks"]:
                options.append(f'{neworks}({opts})')
                anonymous = False

            if anonymous:
                options.append(f'*({opts})')

            entries.append({"path": path, "options": options})

    if not entries:
        raise FileShouldNotExist()
%>
% for export in entries:
${export["path"]}${"\\\n\t"}${"\\\n\t".join(export["options"])}
% endfor
