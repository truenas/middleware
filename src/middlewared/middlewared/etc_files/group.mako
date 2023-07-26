<%
    from middlewared.utils import filter_list

    users_map = {
        i['id']: i
        for i in render_ctx['user.query']
    }

    def get_usernames(group):
        return ','.join([
            users_map[i]['username']
            for i in group['users']
            if i in users_map and users_map[i]['group']['id'] != group['id']
        ])

    def fill_clustered_render_ctx():
        render_ctx['clustered_groups'] = middleware.call_sync('cluster.accounts.group.query')
        render_ctx['clustered_users'] = middleware.call_sync('cluster.accounts.user.query')

    def get_usernames_clustered(group):
        def find_username_by_uid(uid):
            found = filter_list(render_ctx['clustered_users'], [['uid', '=', uid]])
            return found[0]['username'] if found else None

        username_list = []
        for uid in group['users']:
            if not (resolved := find_username_by_uid(uid)):
                continue

            username_list.append(resolved)

        return ','.join(username_list)

    def cluster_healthy():
        if render_ctx.get('cluster_healthy') is None:
            render_ctx['cluster_healthy'] = middleware.call_sync('ctdb.general.healthy')

        return render_ctx['cluster_healthy']

    def check_collisions():
        # check whether the clustered user / group names collide with local ones
        # we have validation to prevent this from happening, but since it has security
        # impact, we need to check for collisions whenever we generate these files.
        local_usernames = set([x['username'] for x in render_ctx['user.query']])
        local_groupnames = set([x['group'] for x in render_ctx['group.query']])
        cluster_usernames = set([x['username'] for x in render_ctx['clustered_users']])
        cluster_groupnames = set([x['group'] for x in render_ctx['clustered_groups']])

        user_overlap = local_usernames & cluster_usernames
        group_overlap = local_groupnames & cluster_groupnames

        if not user_overlap and not group_overlap:
            middleware.call_sync('alert.oneshot_delete', 'ClusteredAccountCollision', None)
            return


        render_ctx['clustered_users'] = []
        render_ctx['clustered_groups'] = []

        msg = (
            'Collision between names for users or groups for clustered and non-clustered '
            'has been detected. This issue will affect file access to the TrueNAS SCALE '
            'cluster and may result in user(s) gaining more or less filesystem access than '
            'the cluster administrator anticipates. '
        )
        if user_overlap:
            msg += (
                f'The following clustered user names collide with local user names: '
                f'{", ".join(user_overlap)}. '
            )
        if group_overlap:
            msg += (
                f'The following clustered group names collide with local group names: '
                f'{", ".join(group_overlap)}. '
            )

        middleware.call_sync('alert.oneshot_create', 'ClusteredAccountCollision', {'errmsg': msg})

    def get_clustered_groups():
        if not cluster_healthy():
            return []

        try:
            fill_clustered_render_ctx()
            for entry in render_ctx['clustered_groups']:
                entry['usernames'] = get_usernames_clustered(entry)

            check_collisions()
            return render_ctx['clustered_groups']
        except Exception:
            middleware.logger.error('Failed to generate local clustered groups.', exc_info=True)
            render_ctx['clustered_groups'] = []
            render_ctx['clustered_users'] = []

        return []

%>\
% for group in filter_list(render_ctx['group.query'], [], {'order_by': ['-builtin', 'gid', 'group']}):
${group['group']}:x:${group['gid']}:${get_usernames(group)}
% endfor
% if render_ctx['cluster.utils.is_clustered']:
% for group in get_clustered_groups():
${group['group']}:x:${group['gid']}:${group['usernames']}
% endfor
% endif
