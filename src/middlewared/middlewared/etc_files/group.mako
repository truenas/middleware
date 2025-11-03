<%
    from middlewared.utils.filter_list import filter_list

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

    def order_groups():
        groups = []
        filtered = filter_list(render_ctx['group.query'], [], {'order_by': ['-builtin', 'group', 'gid']})
        idx = 0
        while idx < len(filtered):
            this_entry = filtered[idx]
            idx += 1
            if idx == len(filtered):
                groups.append(this_entry)
                break

            next_entry = filtered[idx]
            if next_entry['gid'] != this_entry['gid']:
                groups.append(this_entry)
                continue

            match this_entry['gid']:
                # This catches entries with duplicate gids and puts them in
                # Linux order where appropriate. It's unlikely that more
                # entries will be needed, but if the situation arises, this
                # should be expanded for the relevant GIDs (otherwise an error
                # message will be logged)
                case 0:
                    # root (Linux), wheel (FreeBSD)
                    groups.append(this_entry)
                    groups.append(next_entry)
                case 65534:
                    # nobody (FreeBSD), nogroup (Linux)
                    groups.append(next_entry)
                    groups.append(this_entry)
                case _:
                    # default
                    if this_entry['builtin'] and next_entry['builtin']:
                        middleware.logger.error(
                            'Unhandled duplicate builtin gids for %s and %s',
                            this_entry['group'], next_entry['group']
                        )
                    groups.append(this_entry)
                    groups.append(next_entry)

            idx += 1

        return groups
%>\
% for group in order_groups():
${group['group']}:x:${group['gid']}:${get_usernames(group)}
% endfor
