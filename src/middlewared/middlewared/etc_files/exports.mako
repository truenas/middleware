<%
    import ipaddress
    import socket
    import os
    from pathlib import Path
    from contextlib import suppress
    from middlewared.plugins.nfs_.utils import get_domain, leftmost_has_wildcards, get_wildcard_domain
    from middlewared.plugins.pool_.utils import UpdateImplArgs


    def do_map(share, map_type, map_ids, alert_shares):
        output = []
        invalid_name = []

        if usrname := share[f'{map_type}_user']:
            try:
                uid = middleware.call_sync('user.get_user_obj', {'username': usrname})['pw_uid']
                map_ids[f'{map_type}_user'] = uid
                output.append(f'anonuid={uid}')
            except KeyError:
                # report the invalid name
                map_ids[f'{map_type}_user'] = usrname
                invalid_name.append(usrname)

        if grpname := share[f'{map_type}_group']:
            try:
                gid = middleware.call_sync('group.get_group_obj', {'groupname': grpname})['gr_gid']
                map_ids[f'{map_type}_group'] = gid
                output.append(f'anongid={gid}')
            except KeyError:
                # report the invalid name
                map_ids[f'{map_type}_group'] = grpname
                invalid_name.append(grpname)

        if invalid_name:
            try:
                alert_shares[share['path']] += invalid_name
            except KeyError:
                alert_shares[share['path']] = invalid_name
            # Raise KeyError For alert reporting and skip this share
            raise KeyError(f'Missing {invalid_name}') from None

        return output


    def generate_options(share, global_sec, config, alert_shares):
        params = []
        mapall = []
        maproot = []
        map_ids = {
            'maproot_user': -1,
            'maproot_group': -1,
            'mapall_user': -1,
            'mapall_group': -1,
        }

        if share["security"]:
            sec = f'sec={":".join(share["security"])}'
            params.append(sec.lower())
        else:
            sec = f'sec={":".join(global_sec)}'
            params.append(sec)

        if not share["ro"]:
            params.append("rw")

        # report and scrub out shares with invalid names
        mapall = do_map(share, "mapall", map_ids, alert_shares)

        if mapall:
            params.extend(mapall)
            params.append("all_squash")

        maproot = do_map(share, "maproot", map_ids, alert_shares)
        if map_ids['maproot_user'] == 0 and map_ids['maproot_group'] == 0:
            params.append('no_root_squash')
            maproot = []

        if maproot:
            params.extend(maproot)

        if config['allow_nonroot']:
            params.append("insecure")

        return ','.join(params)

    def parse_host(hostname, gaierrors):
        if hostname.startswith('@'):
            # This is a netgroup, skip validation
            return hostname

        if leftmost_has_wildcards(hostname):
            # This is a wildcarded name, skip validation
            return hostname

        try:
            addr = ipaddress.ip_address(hostname)
            return addr.compressed

        except ValueError:
            pass

        try:
            socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            gaierrors.append(hostname)
            return None

        return hostname

    def disable_sharenfs():
        datasets = []
        with open('/etc/exports.d/zfs.exports', 'r') as f:
           for line in f:
               if not line.strip() or line.startswith('#'):
                   continue

               try:
                   ds_name = middleware.call_sync(
                       'zfs.dataset.path_to_dataset',
                       line.rsplit(" ", 1)[0]
                   )
               except Exception:
                   middleware.logger.warning("%s: Dataset lookup failed", line, exc_info=True)
                   continue

               datasets.append(ds_name)

        middleware.logger.warning("Datasets with sharenfs: %s", str(datasets))
        for ds in datasets:
            try:
                middleware.logger.warning("%s: Disable sharenfs", ds)
                middleware.call_sync(
                    'pool.dataset.update_impl',
                    UpdateImplArgs(name=ds, zprops={'sharenfs': 'off'})
                )
            except Exception:
                middleware.logger.warning("%s: Failed to disable sharenfs", ds, exc_info=True)

        return

    def disable_exportsd():

        rv = True

        with suppress(FileExistsError):
            os.mkdir('/etc/exports.d', mode=0o755)

        if 'IMMUTABLE' not in middleware.call_sync('filesystem.stat', '/etc/exports.d')['attributes']:
            middleware.logger.warning('/etc/exports.d: Found in mutable state, expected immutable.')

        # The directory /etc/exports.d should be immutable.
        # If the directory contains files, then we need to delete those files
        # and restore immutable state
        files_in_exportsd = os.listdir('/etc/exports.d')
        if len(files_in_exportsd) > 0:
            middleware.logger.error('Files found in /etc/exports.d: %s', str(files_in_exportsd))

            # Temporary remove immutable to allow file deletion
            middleware.call_sync('filesystem.set_zfs_attributes', {
                'path': '/etc/exports.d',
                'zfs_file_attributes': {'immutable': False}
            })

            # Process zfs.exports first
            if 'zfs.exports' in files_in_exportsd:
                middleware.logger.warning("Disabling sharenfs ZFS property on datasets")
                disable_sharenfs()

            # Remove all files in /etc/exports.d.  NOTE: zfs.exports might now be gone.
            for file in files_in_exportsd:
                filepath = os.path.join('/etc/exports.d', file)
                if os.path.exists(filepath):
                    try:
                        middleware.logger.warning("Removing unexpected file found in exports.d: %s", file)
                        os.remove(filepath)
                    except Exception:
                        middleware.logger.error(
                            "%s: Failed to remove unexpected file in exports.d",
                            file, exc_info=True
                        )

                        # Block NFS start if we fail to cleanup /etc/exports.d
                        rv = False


        # _Always_ exit with /etc/exports.d in immutable state
        middleware.call_sync('filesystem.set_zfs_attributes', {
            'path': '/etc/exports.d',
            'zfs_file_attributes': {'immutable': True}
        })

        # Confirmation
        if 'IMMUTABLE' not in middleware.call_sync('filesystem.stat', '/etc/exports.d')['attributes']:
            rv = False

        return rv

    entries = []
    gaierrors = []
    alert_shares = {}

    config = render_ctx["nfs.config"]
    shares = render_ctx["sharing.nfs.query"]
    poison_exports = not disable_exportsd()

    has_nfs_principal = middleware.call_sync('kerberos.keytab.has_nfs_principal')
    global_sec = middleware.call_sync("nfs.sec", config, has_nfs_principal) or ["sys"]

    for share in shares:
        p = Path(share['path'])
        if not p.exists():
            middleware.logger.info("%s: path does not exist, omitting from NFS exports", p)
            continue

        try:
            params = generate_options(share, global_sec, config, alert_shares)
        except KeyError:
            middleware.logger.info("%s: error in share options, omitting from NFS exports", p)
            continue

        anonymous = True
        options = []
        params += ",no_subtree_check" if p.is_mount() else ",subtree_check"

        if share["expose_snapshots"]:
            params += ",zfs_snapdir"

        for host in share["hosts"]:
            anonymous = False
            export_host = parse_host(host, gaierrors)
            if export_host is None:
                continue

            options.append(f'{host}({params})')

        for network in share["networks"]:
            options.append(f'{network}({params})')
            anonymous = False

        if anonymous:
            options.append(f'*({params})')

        if not options:
            # this may happen if no hosts resolve
            continue

        entries.append({"path": share["path"], "options": options})

    if gaierrors:
        middleware.call_sync(
            'alert.oneshot_create',
            'NFSHostnameLookupFail',
            {'hosts': ', '.join(gaierrors)}
        )
    else:
        middleware.call_sync('alert.oneshot_delete', 'NFSHostnameLookupFail', None)

    if alert_shares:
        disabled_shares = []
        for sharepath, invalid_names in alert_shares.items():
            names = ','.join(invalid_names)
            middleware.logger.warning('%s: Disabling this NFS share. Mapping invalid names: %s', sharepath, names)
            disabled_shares.append(f'({sharepath}: {names})')

        middleware.call_sync("alert.oneshot_create", "NFSexportMappingInvalidNames",
            {'share_list': ','.join(disabled_shares)}
        )
    else:
        middleware.call_sync("alert.oneshot_delete", "NFSexportMappingInvalidNames")


%>
% if poison_exports:
WARNING:
# /etc/exports.d contains unexpected files that could not be removed.
# This message has been added to prevent the NFS service from starting until the
# issue has been resolved.

% else:

% endif
% for export in entries:
"${export["path"]}"${"\\\n\t"}${"\\\n\t".join(export["options"])}
% endfor
